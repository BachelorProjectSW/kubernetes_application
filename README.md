# A Framework for Evaluating Scheduling Strategies

## Architecture

| Service         | Port | Description                                                                                           |
| --------------- | ---- | ----------------------------------------------------------------------------------------------------- |
| `cluster_api` | 8040 | Deployed on each K3s control plane. Manages llama pods, node power, and LLM requests for one cluster. |
| `global_api`  | 8020 | Central scheduler. Distributes incoming LLM questions across all clusters.                            |
| `strato_api`  | 8090 | Main orchestration backend. Starts/stops test runs and exposes results.                               |
| `frontend`    | 8091 | React dashboard for configuring tests and viewing results.                                            |
| `postgresql`  | 5433 | Stores test configurations, structured logs, and results.                                             |

All nodes communicate over a [Tailscale](https://tailscale.com/) VPN.

## Prerequisites

- Docker and Docker Compose
- One or more Raspberry Pi devices running Debian/Ubuntu (for the K3s cluster)
- A Tailscale account

## Getting started

### 1. Set up the K3s cluster

Follow the K3s cluster setup guide in [`src/cluster_api/README.md`](src/cluster_api/README.md). This covers enabling cgroups on Raspberry Pi, installing K3s, joining worker nodes, and deploying the `cluster_api` service to the cluster.

### 2. Start the database

Follow the database setup guide in [`src/db/README.md`](src/db/README.md) to run a local PostgreSQL instance via Docker.

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://strato:strato@<POSTGRES_HOST>:5433/strato
ELECTRICITY_MAPS_API_KEY=<YOUR_KEY>
VITE_CONFIG_API_URL=http://<STRATO_HOST>:8090
```

### 4. Start the backend and frontend

```bash
docker compose up --build
```

This starts `strato_api` on port `8090` and the frontend on port `8091`.

### 5. Deploy the cluster API

On the K3s control plane, apply the manifests from `src/cluster_api/manifest/`:

```bash
kubectl apply -f src/cluster_api/manifest/
```

Or deploy through ArgoCD — see [`src/cluster_api/README.md`](src/cluster_api/README.md).

## Frontend development

Install dependencies:

```bash
cd src/frontend
npm install
```

Start the dev server:

```bash
npm run dev
```

Create a production build:

```bash
npm run build
```

Preview the production build locally:

```bash
npm run preview
```

## Kubernetes quick reference

### Cluster inspection

```bash
kubectl get nodes
kubectl get pods
kubectl get pods -o wide
kubectl get services
```

### Verify required resources

```bash
kubectl get configmap llama-settings llama-init
```

### Node management

```bash
kubectl delete node <NODE_NAME>
```

### Port-forward a pod for local access

Find the pod name:

```bash
kubectl get pods -o wide
```

Forward port `8080` from the pod to your local machine:

```bash
kubectl port-forward pod/<POD_NAME> <LOCAL_PORT>:8080
```

Example:

```bash
kubectl port-forward pod/llama-server-45z67 8080:8080
```

### Query the LLM API

```bash
curl http://127.0.0.1:<LOCAL_PORT>/v1/models

curl http://127.0.0.1:<LOCAL_PORT>/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"model","messages":[{"role":"user","content":"Where is the Red Sea located?"}],"temperature":0.7,"max_tokens":-1}'
```
