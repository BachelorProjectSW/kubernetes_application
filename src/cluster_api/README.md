# K3s Cluster Setup

This guide explains how to set up a small K3s cluster on Raspberry Pi with:
- 1 control plane node
- 1 or more worker nodes

It also shows how to create a Tailscale auth secret in Kubernetes and how to apply the manifests from the `manifest/` folder.

## Prerequisites
- Raspberry Pi devices with a supported Linux distribution
- SSH access to each node
- A Tailscale account if you want to use the Tailscale secret

## Step 1: Enable cgroups

```bash
sudo nano /boot/firmware/cmdline.txt
```

Append the following to the first line (at the end):

```bash
cgroup_memory=1 cgroup_enable=memory```
```

## Step 2: Reboot

Run the following command:

```bash
sudo reboot
```

## Step 3: Install K3s on the control plane/node

Run:

```bash
curl -sfL https://get.k3s.io | sh -
```
Get the join token, to add worker nodes:

```bash
sudo cat /var/lib/rancher/k3s/server/agent-token
```
Save it somewhere, as it is to be used in a later step.

Get the ip address:
```bash
ip a
```

Save this aswell.

Verify the control plane is ready:

```bash
sudo kubectl get nodes
```

## Step 4: Install K3s on the worker nodes, and join them to the cluster

Run this command, replacing the placeholders, with the saved values:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://{IP_FROM_MASTER_NODE}:6443 \
  K3S_TOKEN={TOKEN_FROM_STEP_3} \
  sh -s -
```

## Step 5: Verify the cluster

On the control plane node, check that all nodes joined successfully:
```bash
sudo kubectl get nodes -o wide
```
The following should be shown:
- The control plane node
- All worker nodes

## Step 6: Create the Tailscale auth secret

On the control plane node, create a Kubernetes secret for the Tailscale auth key:

```bash
kubectl create secret generic tailscale-auth \
  --from-literal=TS_AUTHKEY=KEY_FROM_TAILSCALE
```
### To create the Tailscale key

1. Sign in to the Tailscale admin console.
2. Open the Keys page.
3. Generate a new auth key.
4. Copy the key value.
5. Replace KEY_FROM_TAILSCALE with your real key.

Check the [official docs](https://tailscale.com/docs/features/access-control/auth-keys?utm_source=chatgpt.com).

Keep the auth key secret. Do not commit it to Git.

## Step 7: Apply Kubernetes manifests

Create the individual manifest files in a folder named `manifest/`, then run the following command on the control node:

```bash
kubectl apply -f manifest/
```

This applies the files in that folder directly.

As an alternative, the manifests can also be deployed through [ArgoCD](https://argo-cd.readthedocs.io/en/stable/).

### Optional: Install Argo CD on the control plane

If you want to manage deployments through Argo CD instead of applying manifests manually, install Argo CD on the control plane with:

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Check that the pods are running:

```bash
kubectl get pods -n argocd
```

To access the Argo CD UI locally, port-forward the server service:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then open:

```bash
https://localhost:8080
```
To get the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
```
The username is:

```bash
admin
```

## Useful commands

### Check cluster nodes

```bash
kubectl get nodes
```
### Node management

Delete a node:

```bash
kubectl delete node <NODE_NAME>
```

### Check pods

List all pods:

```bash
kubectl get pods
```

List all pods with node placement details:

```bash
kubectl get pods -o wide
```

### Check the K3s service

```bash
kubectl get services
```

