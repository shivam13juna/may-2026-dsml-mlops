"""
aws_ec2_training_dag — train a model on a real EC2 box, orchestrated by Airflow.

WHAT THIS DAG DOES (against REAL AWS)
-------------------------------------
    1. download_from_s3      pull the training data from S3 to the Airflow worker
    2. launch_ec2            start a fresh EC2 instance
    3. wait_for_ec2_running  block until the instance is up and reachable
    4. copy_data_to_ec2      SFTP the dataset onto the instance
    5. train_on_ec2          run the training command over SSH on the instance
    6. upload_model_to_s3    pull the trained model off the box and push it to S3
    7. terminate_ec2         terminate the instance so billing stops

Task graph:

  download_from_s3 ─┐
                    ▼
  launch_ec2 ─► get_instance_id ─► wait_for_ec2_running ─► copy_data_to_ec2 ─►
  train_on_ec2 ─► upload_model_to_s3 ─► terminate_ec2

terminate_ec2 has trigger_rule="all_done", so the instance is ALWAYS torn down —
even if training fails — which is what stops you paying for a stranded machine.

PREREQUISITES (this is not a simulation — it needs real AWS resources)
----------------------------------------------------------------------
- pip install: apache-airflow-providers-amazon, apache-airflow-providers-ssh
- An Airflow connection `aws_default` with credentials (or an instance profile)
  whose IAM covers ec2:RunInstances/DescribeInstances/TerminateInstances and
  s3:GetObject/PutObject on the buckets you configure.
- An EC2 key pair; the matching private .pem readable by the Airflow worker.
- A security group allowing inbound SSH (port 22) from the Airflow worker.
- An AMI with Python (the example installs the training deps itself; user "ubuntu").

CONFIG lives in Airflow Variables (see aws_ec2_training_variables.json):
  aws_region, training_data_bucket, training_data_key, model_bucket, model_key,
  ec2_ami_id, ec2_instance_type, ec2_key_name, ec2_security_group_ids (JSON list),
  ec2_subnet_id, ec2_ssh_user, ec2_ssh_key_file

WHY VARIABLES ARE READ THE WAY THEY ARE
---------------------------------------
NEVER call Variable.get() at the top level of a DAG file. Airflow parses DAG
files constantly and in an isolated context with no execution context, so a
top-level Variable.get() both hammers the metadata DB and fails to resolve at
parse time. Instead:
  - inside @task functions  -> Variable.get(...) at runtime (context exists)
  - inside classic operators -> Jinja "{{ var.value.X }}" / "{{ var.json.X }}"
    which Airflow renders at runtime, not parse time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import Variable, dag, task
from airflow.providers.amazon.aws.hooks.ec2 import EC2Hook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.operators.ec2 import (
    EC2CreateInstanceOperator,
    EC2TerminateInstanceOperator,
)
from airflow.providers.amazon.aws.sensors.ec2 import EC2InstanceStateSensor
from airflow.providers.ssh.hooks.ssh import SSHHook

AWS_CONN_ID = "aws_default"

# Local (Airflow worker) scratch paths for the files in transit.
LOCAL_DATA_PATH  = "/tmp/aws_ec2_training/data.csv"
LOCAL_MODEL_PATH = "/tmp/aws_ec2_training/model.pkl"


@dag(
    dag_id="aws_ec2_training_dag",
    description="Train a model on a transient EC2 instance: S3 -> EC2 -> train -> S3 -> terminate",
    schedule=None,                       # trigger manually
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    # Lets Jinja like "{{ var.json.ec2_security_group_ids }}" render to a real
    # Python list instead of a string (needed for the SecurityGroupIds list).
    render_template_as_native_obj=True,
    tags=["aws", "ec2", "ml"],
)
def aws_ec2_training_dag():

    # Helper: read the SSH/EC2 config and build an SSHHook to the (dynamically
    # created) instance. Called at RUNTIME inside tasks, so Variable.get is safe
    # here. The public DNS name isn't known until the box is up, so we look it
    # up via describe_instances.
    def _ssh_hook(instance_id: str) -> SSHHook:
        region = Variable.get("aws_region", default="ap-south-1")
        ec2 = EC2Hook(aws_conn_id=AWS_CONN_ID, region_name=region, api_type="client_type")
        desc = ec2.conn.describe_instances(InstanceIds=[instance_id])
        host = desc["Reservations"][0]["Instances"][0]["PublicDnsName"]
        if not host:
            raise RuntimeError(f"Instance {instance_id} has no public DNS name yet")
        return SSHHook(
            remote_host=host,
            username=Variable.get("ec2_ssh_user", default="ubuntu"),
            key_file=Variable.get("ec2_ssh_key_file"),
            conn_timeout=30,
            banner_timeout=30,
        )

    def _remote_dir() -> str:
        return f"/home/{Variable.get('ec2_ssh_user', default='ubuntu')}/training"

    # --- 1. Download the training data from S3 to the Airflow worker ---------
    @task
    def download_from_s3() -> str:
        import os
        os.makedirs(os.path.dirname(LOCAL_DATA_PATH), exist_ok=True)
        bucket = Variable.get("training_data_bucket")
        key = Variable.get("training_data_key", default="raw/iris.csv")
        hook = S3Hook(aws_conn_id=AWS_CONN_ID)
        tmp = hook.download_file(key=key, bucket_name=bucket)   # returns a temp path
        os.replace(tmp, LOCAL_DATA_PATH)                        # move to a known path
        print(f"Downloaded s3://{bucket}/{key} -> {LOCAL_DATA_PATH}")
        return LOCAL_DATA_PATH

    # --- 2. Launch a fresh EC2 instance -------------------------------------
    # Classic operator: every value comes from a Variable via Jinja (rendered at
    # runtime). EC2CreateInstanceOperator pushes the new instance id(s) to XCom.
    launch_ec2 = EC2CreateInstanceOperator(
        task_id="launch_ec2",
        aws_conn_id=AWS_CONN_ID,
        region_name="{{ var.value.aws_region }}",
        image_id="{{ var.value.ec2_ami_id }}",
        max_count=1,
        min_count=1,
        config={
            "InstanceType": "{{ var.value.ec2_instance_type }}",
            "KeyName": "{{ var.value.ec2_key_name }}",
            "SecurityGroupIds": "{{ var.json.ec2_security_group_ids }}",
            "SubnetId": "{{ var.value.ec2_subnet_id }}",
            "TagSpecifications": [{
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "airflow-ec2-training"}],
            }],
        },
        wait_for_completion=True,        # return only once the instance is 'running'
    )

    # launch_ec2 returns a list of instance ids; pull out the single one we made.
    # (An XComArg can't be int-indexed directly, so do it in a tiny task — this
    # also wires the dependency on launch_ec2 automatically.)
    @task
    def get_instance_id(instance_ids: list[str]) -> str:
        return instance_ids[0]

    # --- 3. Belt-and-suspenders: also gate on the 'running' state ------------
    wait_for_ec2_running = EC2InstanceStateSensor(
        task_id="wait_for_ec2_running",
        aws_conn_id=AWS_CONN_ID,
        region_name="{{ var.value.aws_region }}",
        instance_id="{{ ti.xcom_pull(task_ids='get_instance_id') }}",
        target_state="running",
        poke_interval=15,
        timeout=600,
    )

    # --- 4. Copy the dataset onto the instance via SFTP ---------------------
    @task
    def copy_data_to_ec2(local_path: str, instance_id: str) -> str:
        remote_data = f"{_remote_dir()}/data.csv"
        with _ssh_hook(instance_id).get_conn() as ssh:
            ssh.exec_command(f"mkdir -p {_remote_dir()}")
            with ssh.open_sftp() as sftp:
                sftp.put(local_path, remote_data)
        print(f"Uploaded {local_path} -> {instance_id}:{remote_data}")
        return remote_data

    # --- 5. Run the training command on the instance over SSH ---------------
    @task
    def train_on_ec2(remote_data_path: str, instance_id: str) -> str:
        remote_model = f"{_remote_dir()}/model.pkl"
        train_cmd = (
            f"set -euo pipefail; cd {_remote_dir()}; "
            "python3 -m pip install --quiet --user scikit-learn pandas; "
            "python3 - <<'PY'\n"
            "import pandas as pd, pickle\n"
            "from sklearn.ensemble import RandomForestClassifier\n"
            "from sklearn.model_selection import train_test_split\n"
            "from sklearn.metrics import accuracy_score\n"
            f"df = pd.read_csv('{remote_data_path}')\n"
            "X, y = df.drop(columns='target'), df['target']\n"
            "Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42)\n"
            "m = RandomForestClassifier(random_state=42).fit(Xtr, ytr)\n"
            "print('accuracy =', accuracy_score(yte, m.predict(Xte)))\n"
            f"pickle.dump(m, open('{remote_model}', 'wb'))\n"
            "PY"
        )
        with _ssh_hook(instance_id).get_conn() as ssh:
            _stdin, stdout, stderr = ssh.exec_command(train_cmd)
            exit_status = stdout.channel.recv_exit_status()   # blocks until done
            print("STDOUT:\n" + stdout.read().decode())
            err = stderr.read().decode()
            if err:
                print("STDERR:\n" + err)
            if exit_status != 0:
                raise RuntimeError(f"Training failed on {instance_id} (exit {exit_status})")
        print(f"Training finished on {instance_id}; model at {remote_model}")
        return remote_model

    # --- 6. Pull the model off the box and publish it to S3 -----------------
    @task
    def upload_model_to_s3(remote_model_path: str, instance_id: str) -> str:
        import os
        os.makedirs(os.path.dirname(LOCAL_MODEL_PATH), exist_ok=True)
        with _ssh_hook(instance_id).get_conn() as ssh, ssh.open_sftp() as sftp:
            sftp.get(remote_model_path, LOCAL_MODEL_PATH)     # EC2 -> worker
        bucket = Variable.get("model_bucket")
        key = Variable.get("model_key", default="models/model.pkl")
        S3Hook(aws_conn_id=AWS_CONN_ID).load_file(            # worker -> S3
            filename=LOCAL_MODEL_PATH, key=key, bucket_name=bucket, replace=True)
        uri = f"s3://{bucket}/{key}"
        print(f"Published model -> {uri}")
        return uri

    # --- 7. Terminate the instance (ALWAYS, even on failure) ----------------
    terminate_ec2 = EC2TerminateInstanceOperator(
        task_id="terminate_ec2",
        aws_conn_id=AWS_CONN_ID,
        region_name="{{ var.value.aws_region }}",
        instance_ids="{{ ti.xcom_pull(task_ids='launch_ec2') }}",
        wait_for_completion=True,
        trigger_rule="all_done",          # tear down regardless of upstream result
    )

    # ---- Wiring -----------------------------------------------------------
    instance_id = get_instance_id(launch_ec2.output)
    data_path   = download_from_s3()

    instance_id >> wait_for_ec2_running   # sensor pulls the id via XCom template

    remote_data  = copy_data_to_ec2(data_path, instance_id)
    wait_for_ec2_running >> remote_data    # don't SSH until the box is running

    remote_model = train_on_ec2(remote_data, instance_id)
    model_uri    = upload_model_to_s3(remote_model, instance_id)

    model_uri >> terminate_ec2            # terminate after upload (or any failure)


aws_ec2_training_dag()
