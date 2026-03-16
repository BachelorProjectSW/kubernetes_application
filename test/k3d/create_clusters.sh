#!/bin/bash

set -e

# Denmark cluster
k3d cluster delete devcluster-dk || true

k3d cluster create --config test/k3d/cluster_dk.yaml

k3d kubeconfig get devcluster-dk > src/cluster_api/auth/k3d-devcluster-dk.yaml


# Portugal cluster
k3d cluster delete devcluster-po || true

k3d cluster create --config test/k3d/cluster_po.yaml

k3d kubeconfig get devcluster-po > src/cluster_api/auth/k3d-devcluster-po.yaml
