#!/bin/bash

set -e

docker build -t kube-api-server .

docker run --rm \
  -e KUBECONFIG=/app/src/cluster_api/auth/k3d-devcluster.yaml \
  kube-api-server \
  pytest /app/test
