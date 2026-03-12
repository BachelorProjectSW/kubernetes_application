#!/bin/bash

set -e

#Download k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

#Get CPU type
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        C_ARCH="amd64"
        ;;
    aarch64 | arm64)
        C_ARCH="arm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac


#install kubectl
curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/$C_ARCH/kubectl
chmod +x kubectl
sudo mv kubectl /usr/local/bin/


