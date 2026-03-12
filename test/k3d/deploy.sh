#!/bin/bash

set -e

export KUBECONFIG=src/cluster_api/auth/k3d-devcluster.yaml

kubectl wait --for=condition=Ready nodes --all --timeout=120s

kubectl apply -f src/cluster_api/manifest/
