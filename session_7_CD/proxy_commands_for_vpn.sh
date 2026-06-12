NO_PROXY=".amazonaws.com" aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 796973487349.dkr.ecr.us-west-2.amazonaws.com

jmeter -N "localhost|127.0.0.1|127.*|::1"

