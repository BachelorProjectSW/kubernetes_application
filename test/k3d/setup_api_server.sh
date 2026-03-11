#!/bin/bash

set -e

sudo apt install docker.io -y
sudo systemctl start docker

docker build -t kube-api-server .

docker run --network=host kube-api-server:latest
