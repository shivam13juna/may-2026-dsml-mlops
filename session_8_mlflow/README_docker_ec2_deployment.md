# Deploy a Docker Image on AWS EC2

This guide explains how to create an EC2 instance from the AWS Console and deploy a Docker image on it.

## Assumptions

You already have a Docker image available in one of these ways:

1. The image is pushed to Docker Hub.
2. The image is pushed to AWS ECR.
3. The image exists locally on your machine and can be exported as a `.tar` file.

Replace placeholders such as `YOUR_EC2_PUBLIC_IP`, `YOUR_IMAGE_NAME`, `YOUR_CONTAINER_PORT`, and `YOUR_ACCOUNT_ID` with your actual values.

---

## 1. Create an EC2 Instance from AWS Console

Go to:

```text
AWS Console → EC2 → Instances → Launch instances
```

### Basic Settings

Set the instance name:

```text
my-docker-server
```

Choose an AMI:

```text
Ubuntu Server 24.04 LTS
```

Recommended instance type for testing:

```text
t3.micro
```

For heavier applications, use:

```text
t3.small
t3.medium
```

---

## 2. Create or Select a Key Pair

In the **Key pair** section, create or select an existing key pair.

Example:

```text
my-ec2-key.pem
```

Download the `.pem` file and keep it safe.

On your local machine, run:

```bash
chmod 400 ~/Downloads/my-ec2-key.pem
```

This gives the private key the correct permissions for SSH.

---

## 3. Configure Security Group

In the **Network settings** section, create a new security group.

Add these inbound rules:

| Type | Port | Source | Purpose |
|---|---:|---|---|
| SSH | 22 | My IP | SSH into EC2 |
| HTTP | 80 | Anywhere `0.0.0.0/0` | Public web access |
| HTTPS | 443 | Anywhere `0.0.0.0/0` | SSL/HTTPS |
| Custom TCP | Your app port, for example `8000` | Anywhere or My IP | Only if exposing app directly |

For production, prefer exposing only ports `80` and `443`.

Avoid exposing backend ports directly unless needed.

---

## 4. Launch the Instance

Click:

```text
Launch instance
```

Then go to:

```text
EC2 → Instances
```

Wait until the instance shows:

```text
Instance state: Running
Status checks: 2/2 checks passed
```

Copy the instance's **Public IPv4 address**.

---

## 5. Connect to EC2

From your local terminal:

```bash
ssh -i ~/Downloads/my-ec2-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Example:

```bash
ssh -i ~/Downloads/my-ec2-key.pem ubuntu@13.201.45.100
```

For Ubuntu EC2 instances, the default username is usually:

```text
ubuntu
```

---

## 6. Install Docker on EC2

Run these commands inside the EC2 terminal.

Update packages:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
```

Add Docker's official GPG key:

```bash
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg
```

Add Docker's repository:

```bash
echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Install Docker:

```bash
sudo apt-get update

sudo apt-get install -y \
docker-ce \
docker-ce-cli \
containerd.io \
docker-buildx-plugin \
docker-compose-plugin
```

Check Docker:

```bash
sudo docker --version
sudo docker run hello-world
```

---

## 7. Optional: Run Docker Without `sudo`

Add the Ubuntu user to the Docker group:

```bash
sudo usermod -aG docker ubuntu
```

Exit the SSH session:

```bash
exit
```

Reconnect:

```bash
ssh -i ~/Downloads/my-ec2-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Now you should be able to run Docker without `sudo`:

```bash
docker ps
```

---

# Deployment Options

Choose one of the following options depending on where your Docker image is stored.

---

## Option A: Deploy Image from Docker Hub

Example image:

```text
yourdockerhubuser/my-app:latest
```

Login to Docker Hub:

```bash
docker login
```

Pull the image:

```bash
docker pull yourdockerhubuser/my-app:latest
```

Run the container:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8000 \
  yourdockerhubuser/my-app:latest
```

Here:

```text
-p 80:8000
```

means:

```text
EC2 public port 80 → container internal port 8000
```

If your app listens inside the container on port `5000`, use:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:5000 \
  yourdockerhubuser/my-app:latest
```

If your app listens on port `3000`, use:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:3000 \
  yourdockerhubuser/my-app:latest
```

---

## Option B: Deploy Local Docker Image to EC2

On your local machine, save the image as a `.tar` file:

```bash
docker save my-app:latest -o my-app.tar
```

Copy it to EC2:

```bash
scp -i ~/Downloads/my-ec2-key.pem my-app.tar ubuntu@YOUR_EC2_PUBLIC_IP:/home/ubuntu/
```

SSH into EC2:

```bash
ssh -i ~/Downloads/my-ec2-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

Load the Docker image:

```bash
docker load -i my-app.tar
```

Check the image name:

```bash
docker images
```

Run the container:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8000 \
  my-app:latest
```

Change `8000` if your container listens on a different internal port.

---

## Option C: Deploy Image from AWS ECR

Attach an IAM role to the EC2 instance with this policy:

```text
AmazonEC2ContainerRegistryReadOnly
```

Install AWS CLI if needed:

```bash
sudo apt-get update
sudo apt-get install -y awscli
```

Login to ECR:

```bash
aws ecr get-login-password --region ap-south-1 | \
docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com
```

Pull the image:

```bash
docker pull YOUR_ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/my-app:latest
```

Run the container:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8000 \
  YOUR_ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/my-app:latest
```

---

# 8. Check Whether the Container Is Running

Check running containers:

```bash
docker ps
```

View logs:

```bash
docker logs -f my-app
```

Test from inside EC2:

```bash
curl http://localhost
```

Test from your browser:

```text
http://YOUR_EC2_PUBLIC_IP
```

Example:

```text
http://13.201.45.100
```

---

# 9. Common Debugging Steps

## Check Container Port Mapping

Run:

```bash
docker ps
```

Look at the `PORTS` column.

You should see something like:

```text
0.0.0.0:80->8000/tcp
```

This means public port `80` is mapped to container port `8000`.

---

## Check Container Logs

```bash
docker logs my-app
```

If the app crashed, the error usually appears here.

---

## Check Security Group

In AWS Console, go to:

```text
EC2 → Instances → Select instance → Security → Security groups → Inbound rules
```

Make sure port `80` is open.

For HTTPS, make sure port `443` is open.

---

## Check App Binding

Inside your Docker app, the server must bind to:

```text
0.0.0.0
```

Not:

```text
127.0.0.1
```

If your app binds only to `127.0.0.1`, it may work inside the container but not from outside.

### Flask Example

```python
app.run(host="0.0.0.0", port=8000)
```

### FastAPI / Uvicorn Example

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Streamlit Example

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Then run the Docker container like this:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8501 \
  my-streamlit-app:latest
```

---

# 10. Update the Deployment Later

Stop the old container:

```bash
docker stop my-app
docker rm my-app
```

Pull the latest image:

```bash
docker pull yourdockerhubuser/my-app:latest
```

Run the new container:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8000 \
  yourdockerhubuser/my-app:latest
```

---

# 11. Minimum Deployment Command

Once Docker is installed, the core deployment command is:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:YOUR_CONTAINER_PORT \
  YOUR_IMAGE_NAME:TAG
```

Example:

```bash
docker run -d \
  --name my-app \
  --restart unless-stopped \
  -p 80:8000 \
  my-app:latest
```

---

# 12. Recommended Production Improvements

For a simple demo, the above setup is enough.

For a more production-ready setup, consider:

1. Allocate an **Elastic IP** so the public IP does not change after stopping and starting the instance.
2. Put **Nginx** in front of the container.
3. Use **HTTPS** with Certbot.
4. Store secrets in environment variables, not inside the Docker image.
5. Use an IAM role for AWS access instead of storing AWS keys on the server.
6. Consider **ECS Fargate** instead of manually managing Docker on EC2 for serious production deployments.

---

# 13. Useful Commands

List containers:

```bash
docker ps
```

List all containers, including stopped ones:

```bash
docker ps -a
```

View logs:

```bash
docker logs -f my-app
```

Stop container:

```bash
docker stop my-app
```

Remove container:

```bash
docker rm my-app
```

Restart container:

```bash
docker restart my-app
```

List Docker images:

```bash
docker images
```

Remove image:

```bash
docker rmi IMAGE_ID
```

Check disk usage:

```bash
df -h
```

Clean unused Docker resources:

```bash
docker system prune
```

Use this carefully because it removes unused containers, networks, images, and build cache.

---

# 14. Checklist

Before testing in the browser, confirm:

- EC2 instance is running.
- Security group allows inbound traffic on port `80`.
- Docker is installed.
- Container is running.
- Correct port mapping is used.
- App binds to `0.0.0.0`.
- Browser URL uses the EC2 public IP.

Final browser test:

```text
http://YOUR_EC2_PUBLIC_IP
```
