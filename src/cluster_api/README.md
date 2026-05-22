# Cluster API

The `cluster_api` service runs on the K3s control plane of each Raspberry Pi cluster. It is responsible for:

- Managing `llama.cpp` pod lifecycle (start, cancel, restart)
- Powering worker nodes on and off based on demand or idle time
- Receiving cluster configuration from the `global_api`
- Routing LLM requests to the correct llama pod

It is deployed as a Kubernetes `Deployment` on the control plane node and exposes port `8040`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/get_cluster_working_nodes` | List worker nodes known to this cluster |
| `GET` | `/get_cluster_information` | Return the active cluster configuration |
| `POST` | `/set_config` | Load a new cluster configuration |
| `POST` | `/handle_llm_request` | Forward an LLM question to the appropriate pod |
| `POST` | `/turn_on_nodes/` | Power on a number of worker nodes |
| `POST` | `/turn_off_nodes/` | Power off a number of worker nodes |
| `POST` | `/turn_off_idle_nodes/` | Power off nodes that have been idle too long |
| `POST` | `/cancel_all_llama_pods` | Delete all running llama pods so they restart cleanly |

---

## K3s Cluster Setup

This section covers setting up a K3s cluster on Raspberry Pi hardware that this service will run on.

### Prerequisites

- Raspberry Pi devices with a supported Linux distribution
- SSH access to each node
- A [Tailscale](https://tailscale.com/) account for VPN networking between nodes

### Step 1: Enable cgroups

On each Raspberry Pi, edit the boot command line:

```bash
sudo nano /boot/firmware/cmdline.txt
```

Append the following to the **first line** (do not create a new line):

```
cgroup_memory=1 cgroup_enable=memory
```

### Step 2: Reboot

```bash
sudo reboot
```

### Step 3: Install K3s on the control plane node

```bash
curl -sfL https://get.k3s.io | sh -
```

Retrieve the join token for worker nodes:

```bash
sudo cat /var/lib/rancher/k3s/server/agent-token
```

Retrieve the control plane IP address:

```bash
hostname -I
```

Save both values — you will need them in the next step.

Verify the control plane is ready:

```bash
sudo kubectl get nodes
```

### Step 4: Join worker nodes to the cluster

On each worker node, run the following (replacing the placeholders with the values from Step 3):

```bash
sudo apt install curl -y

curl -sfL https://get.k3s.io | \
  K3S_URL=https://<CONTROL_PLANE_IP>:6443 \
  K3S_TOKEN=<TOKEN_FROM_STEP_3> \
  sh -s -
```

### Step 5: Verify the cluster

On the control plane, confirm all nodes have joined:

```bash
sudo kubectl get nodes -o wide
```

The output should list the control plane node and all worker nodes.

### Step 6: Create the Tailscale auth secret

Create a Kubernetes secret for the Tailscale auth key. To generate a key:

1. Sign in to the [Tailscale admin console](https://login.tailscale.com/admin/settings/keys).
2. Open the **Keys** page and generate a new auth key.
3. Copy the key value and run:

```bash
kubectl create secret generic tailscale-auth \
  --from-literal=TS_AUTHKEY=<YOUR_TAILSCALE_AUTH_KEY>
```

> **Keep the auth key secret. Do not commit it to Git.**

### Step 7: Deploy the cluster API

Apply all manifests from the `manifest/` folder on the control plane:

```bash
kubectl apply -f manifest/
```

#### Optional: Deploy through Argo CD

If you prefer GitOps-style deployments, install Argo CD on the control plane:

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Verify the pods are running:

```bash
kubectl get pods -n argocd
```

Access the Argo CD UI locally:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then open `https://localhost:8080` in your browser.

Retrieve the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

The default username is `admin`.

---

## Useful commands

```bash
# Check cluster nodes
kubectl get nodes

# Check pods
kubectl get pods
kubectl get pods -o wide

# Check services
kubectl get services

# Delete a node
kubectl delete node <NODE_NAME>
```
