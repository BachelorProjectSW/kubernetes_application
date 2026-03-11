#!/bin/bash

set -e

kubectl wait --for=condition=Ready nodes --all --timeout=60s

kubectl apply -f src/cluster_api/manifest/

