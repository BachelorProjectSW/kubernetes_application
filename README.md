# bachelor

Install k3s guide on rpi

Step 1)
Install the master node:
append "cgroup_memory=1 cgroup_enable=memory" to the first line in /boot/firmware/cmdline.txt
ensure to edit with sudo, as the file is read-only:
sudo vim /boot/firmware/cmdline.txt
before:
cfg80211.ieee80211_regdom=DK
after:
cfg80211.ieee80211_regdom=DK cgroup_memory=1 cgroup_enable=memory

Step 2)
Reboot

Step 3)
Run "curl -sfL https://get.k3s.io | sh -"

step 4)
#Get the token (which should be used from the working nodes
cat /var/lib/rancher/k3s/server/agent-token

step 5)
#Get the ip address from the master node
ip a 

step 6) 
Setup working nodes/agents:
curl -sfL https://get.k3s.io | K3S_URL=https://{IP_FROM_MASTER_NODE}:6443 K3S_TOKEN={TOKEN_FROM_STEP_4} K3S_NODE_NAME="{UNIQUE_NODE_NAME}" sh -s -


___________
Get API authentication

step 1)
Copy the auth file to fixed place
sudo cp /etc/rancher/k3s/k3s.yaml src/cluster_api/auth

Make it read/write
sudo chmod 644 src/cluster_api/auth/k3s.yaml

_____
Setup docker for getting data from kubernetes network.

step 1)
Install docker
sudo apt update
sudo apt install docker.io -y

step 2)
start Docker and enable it at boot
sudo systemctl start docker
sudo systemctl enable docker

step 3)
add docker to groups
sudo usermod -aG docker $USER
sudo reboot 

step 4)
Build docker file:
cd kubernetes
docker build -t kube-api-server .

step 5)
Run api server (on host network, as otherwise docker will create its own local network):
docker run --network=host kube-api-server
_____


## Kubernetes quick commands

Use the commands below to inspect the cluster, verify required resources, connect to the server locally, and test the API.

## Cluster inspection

List all nodes:

```bash
kubectl get nodes
```

List all pods:

```bash
kubectl get pods
```

List all pods with node placement details:

```bash
kubectl get pods -o wide
```

List all services:

```bash
kubectl get services
```

## Resource checks

Confirm that the required configmaps are present:

```bash
kubectl get configmap llama-settings llama-init
```

## Node management

Delete a node:

```bash
kubectl delete node <NODE_NAME>
```

## Local access with port-forwarding

Find the target server pod:

```bash
kubectl get pods -o wide
```

Forward the pod’s port `8080` to your local machine:

```bash
kubectl port-forward pod/<SERVER_NAME> <LOCAL_PORT>:8080
```

Example:

```bash
kubectl port-forward pod/llama-server-45z67 8080:8080
```

Alternative example:

```bash
kubectl port-forward pod/llama-server-r5mdv 8888:8080
```

## API verification

Query the models endpoint:

```bash
curl http://127.0.0.1:<LOCAL_PORT>/v1/models
```

Send a sample chat request:

```bash
curl http://127.0.0.1:<LOCAL_PORT>/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"model","messages":[{"role":"user","content":"Where is the Red Sea located?"}],"temperature":0.7,"max_tokens":-1}'
```


# Frontend setup

The developer is expected to have Node.js installed.

Change into the frontend app directory:
```bash
cd src/cluster_frontend
```

Install dependencies:
```bash
npm install
```

Next, run the live dev server:
```bash
npm run dev
```

Create a production build:
```bash
npm run build
```

Preview the production build locally
```bash
npm run preview
```


