#!/bin/bash

set -e

docker build -t kube-api-server .

docker run --network=host kube-api-server:latest
