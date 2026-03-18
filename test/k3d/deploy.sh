#!/bin/bash

set -e

# Get all cluster names
source test/k3d/cluster_name_list.sh

for cluster_name in ${CLUSTER_NAMES[@]}; do
	export KUBECONFIG="src/cluster_api/auth/k3d-devcluster-${cluster_name}.yaml"
	echo "waiting for nodes"
	kubectl wait --for=condition=Ready nodes --all --timeout=120s
	echo "nodes are ready"
	kubectl apply -f src/cluster_api/manifest/
	echo "applying ${cluster_name} manifest"
	kubectl wait --for=condition=Ready pod -l name=llama-server --timeout=180s
	echo "all pods ready"
done
