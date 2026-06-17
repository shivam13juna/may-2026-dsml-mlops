# Airflow demo — setup & run log

A complete, reproducible record of how this Airflow demo was installed and run,
including the environment paths and the gotchas hit along the way. Follow it
top to bottom to recreate everything from scratch.

> Note: this documents **Apache Airflow** (the workflow orchestrator used in
> this demo). The commands below are exactly what was run on this machine.

---

## 0. Environment / facts

| Thing | Value |
|-------|-------|
| OS | macOS (Darwin), Apple Silicon |
| Virtualenv | `/Users/shivam13juna/Documents/virtual_envs/airflow` |
| Python | 3.13.2 (inside that venv) |
| Airflow | 3.2.2 |
| scikit-learn / pandas | 1.8.0 / 2.3.3 |
| Demo folder (= `AIRFLOW_HOME`) | `/Users/shivam13juna/Documents/scaler/mlops/airflow_demo` |

The `airflow` venv already existed (created with `python -m venv`). Everything
else below was installed/configured into it.

---

## 1. Install Airflow into the venv

Airflow has a large dependency tree, so it must be installed **with a
constraints file** that pins every transitive dependency to a combination the
Airflow team tested. The constraints URL encodes both the Airflow version and
the Python version (`constraints-3.13.txt`).

```bash
VENV=/Users/shivam13juna/Documents/virtual_envs/airflow/bin
AIRFLOW_VERSION=3.2.2
PY=3.13

$VENV/pip install \
  "apache-airflow==${AIRFLOW_VERSION}" scikit-learn pandas \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PY}.txt"
```

`scikit-learn` and `pandas` are added because the demo DAG trains real models;
they aren't required by Airflow itself.

Verify:

```bash
$VENV/python -c "import airflow, sklearn, pandas; print(airflow.__version__)"
# -> 3.2.2
```

---

## 2. Choose an AIRFLOW_HOME (the important "path" step)

By default Airflow uses `~/airflow` as its **`AIRFLOW_HOME`** — the folder that
holds its config (`airflow.cfg`), metadata database (`airflow.db`), logs, and
the `dags/` folder it scans. On this machine `~/airflow` already contained an
**old (2.x) config**, which produced deprecation warnings on every command.

To keep this demo isolated and clean, point `AIRFLOW_HOME` at the demo folder
instead. Set these env vars in **every shell** that runs an airflow command:

```bash
export AIRFLOW_HOME=/Users/shivam13juna/Documents/scaler/mlops/airflow_demo
export AIRFLOW__CORE__DAGS_FOLDER=$AIRFLOW_HOME/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=False   # hide Airflow's bundled example DAGs
```

- `AIRFLOW_HOME` → where Airflow stores its state (here, this folder).
- `AIRFLOW__CORE__DAGS_FOLDER` → where it looks for DAG files (`dags/`).
- `AIRFLOW__CORE__LOAD_EXAMPLES=False` → so the UI shows only our `ml_pipeline`.

> Any config key can be set via an env var using the pattern
> `AIRFLOW__<SECTION>__<KEY>`. That's why `[core] dags_folder` becomes
> `AIRFLOW__CORE__DAGS_FOLDER`.

The `run_airflow.sh` script sets all of these for you, so for the UI you don't
have to remember them.

---

## 3. Initialize the metadata database

Airflow needs a database (SQLite by default, created inside `AIRFLOW_HOME`).
This step creates all its tables:

```bash
$VENV/airflow db migrate
# -> "Database migration done!"  (creates airflow.db here)
```

---

## 4. Register & verify the DAG

In Airflow 3.x, `airflow dags list` reads from the **database**, which is
populated by the DAG processor — a fresh DB shows "No data found" until the
folder has been parsed. Force a parse with `reserialize`:

```bash
$VENV/airflow dags reserialize     # parses dags/ and writes them to the DB
$VENV/airflow dags list            # should now show: ml_pipeline
```

---

## 5. Run the whole pipeline once (no UI)

`airflow dags test` parses **and executes** the DAG in-process — the fastest way
to confirm it works end to end:

```bash
$VENV/airflow dags test ml_pipeline
```

Expected (trimmed) output:

```
Saved 150 rows to /tmp/airflow_ml_demo/iris.csv
LogisticRegression accuracy = 1.000
DecisionTree accuracy = 1.000
Winner     : LogisticRegression (1.000)
  Best model : LogisticRegression
DagRun Finished: ... state=success
```

---

## 6. Run the Web UI

```bash
bash run_airflow.sh        # then open http://localhost:8080  (user: admin)
```

`airflow standalone` boots everything (api-server/UI, scheduler, dag-processor,
triggerer) and prints the admin password on first run. The password is also
saved in:

```
airflow_demo/simple_auth_manager_passwords.json.generated
```

In the UI: open the **`ml_pipeline`** DAG → toggle it **on** → click **Trigger**
→ watch the **Graph** turn green. Stop the server with `Ctrl-C`.

---

## 7. Gotchas hit along the way (read this)

1. **`airflow standalone` needs the venv on `PATH`, not just a full path.**
   `standalone` launches the scheduler/api-server/etc. as child processes by
   calling the **bare command `airflow`**. If you invoke it as
   `/full/path/to/airflow standalone` without the venv's `bin` on `PATH`, the
   children fail with:

   ```
   FileNotFoundError: [Errno 2] No such file or directory: 'airflow'
   ```

   Fix (this is what `run_airflow.sh` does):

   ```bash
   export PATH="/Users/shivam13juna/Documents/virtual_envs/airflow/bin:$PATH"
   airflow standalone
   ```

   (Equivalently: `source .../airflow/bin/activate` first, then `airflow standalone`.)

2. **Deprecation warnings about `[webserver]` options moving to `[api]`.**
   These come from the *old* `~/airflow/airflow.cfg`. They disappear once
   `AIRFLOW_HOME` points at this demo folder (which gets a fresh 3.2.2 config).

3. **`Could not import graphviz` warning.** Harmless — only affects rendering a
   DAG graph to an image *from the CLI*. The web UI's Graph view does not need it.

4. **Python 3.13.** Airflow 3.2.x supports Python 3.13; older Airflow 2.x lines
   generally do not. That's why this demo uses Airflow 3.2.2.

---

## 8. Reset to a clean slate

```bash
cd /Users/shivam13juna/Documents/scaler/mlops/airflow_demo
rm -rf airflow.db airflow.cfg logs/ simple_auth_manager_passwords.json.generated
# then redo steps 3-5
```
