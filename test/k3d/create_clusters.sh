#!/bin/bash

set -e

# Get cluster names
source test/k3d/cluster_name_list.sh

k3d cluster delete -a || true

for cluster_name in ${CLUSTER_NAMES[@]}; do
	k3d cluster create --config test/k3d/cluster_configs/cluster-${cluster_name}.yaml
	
	k3d kubeconfig get devcluster-${cluster_name} > src/cluster_api/auth/k3d-devcluster-${cluster_name}.yaml

	k3d image import llama-server-arm64 -c devcluster-${cluster_name}
done
