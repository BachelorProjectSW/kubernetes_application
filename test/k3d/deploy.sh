#!/bin/bash

set -e

kubectl apply -f manifests/

kubectl wait --for=condition=available deployment --all --timeout=300s
