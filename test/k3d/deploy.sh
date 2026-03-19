#!/bin/bash

set -e

# Get all cluster names
source test/k3d/cluster_name_list.sh

for cluster_name in ${CLUSTER_NAMES[@]}; do
	export KUBECONFIG="src/cluster_api/auth/k3d-devcluster-${cluster_name}.yaml"
	
	kubectl wait --for=condition=Ready nodes --all --timeout=120s
	
	kubectl apply -f src/cluster_api/manifest/
	
	kubectl wait --for=condition=Ready pod -l name=llama-server --timeout=180s
done
