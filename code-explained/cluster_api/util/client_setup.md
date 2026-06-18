# `src/cluster_api/util/client_setup.py` — authenticating to Kubernetes

This tiny file is the **single place the cluster API gets a Kubernetes client**. Every K8s
operation (listing nodes, listing llama pods) starts by calling `get_api_client()`. Read the
`kubernetes-primer.md` first if "K8s client" / "in-cluster" / "kubeconfig" are unfamiliar.

```python
3   from kubernetes import client, config
6   def get_api_client():
24      try:
25          config.load_incluster_config()
26      except config.ConfigException:
27          kubeconfig = os.environ.get("KUBECONFIG")
28          if not kubeconfig:
29              raise RuntimeError("KUBECONFIG is not set")
30          config.load_kube_config(config_file=kubeconfig)
32      return client.CoreV1Api()
```

- **Line 3** — `client` (objects to *call* the K8s API) and `config` (functions to *load
  credentials*) from the official `kubernetes` Python library.
- **Line 25 — try in-cluster first.** `load_incluster_config()` reads the credentials
  Kubernetes **automatically injects into every pod** (a token + the API server address,
  mounted into the container's filesystem). This succeeds **only when the cluster API is
  itself running as a pod inside the cluster**, the production case. No config files, no env
  vars needed; the pod can talk to its own cluster out of the box.
- **Lines 26–30 — fall back to kubeconfig.** If we're **not** in a pod (local dev / k3d),
  `load_incluster_config()` raises `ConfigException`. We catch it and instead load a
  **kubeconfig file** whose path comes from the `KUBECONFIG` env var. If that var isn't set,
  we fail loudly with a clear `RuntimeError`. A kubeconfig is the credentials file `kubectl`
  uses, pointing at a specific cluster.
- **Line 32 — return a `CoreV1Api` client.** `CoreV1Api` is the K8s API group covering the
  "core" objects: **nodes, pods, services, configmaps**. That's exactly what we need (we list
  nodes and pods). Other API groups exist (apps for Deployments/DaemonSets, etc.) but the
  cluster API only reads core objects, so this one client is enough.

## Why this pattern matters

This is the **standard "works inside and outside the cluster" idiom**. The same code path
serves:
- **production** (Pi cluster) → in-cluster credentials, automatic,
- **local k3d tests** → `KUBECONFIG` pointing at the k3d cluster.

So nobody has to change code between dev and prod; the environment decides which branch runs.
This is the cluster-API equivalent of the `k3d` flag, one codebase, two worlds.

## Defense-worthy points
- **One client factory, two auth modes** (in-cluster vs KUBECONFIG), chosen by try/except.
- **`CoreV1Api`** = the nodes/pods/services API; that's all the cluster API needs.
- A **fresh client is created on every call** (no caching here). Cheap enough, but worth
  noting, callers like `build_worker_nodes` and `populate_host_port` each make their own.

**Used by:** `util/cluster_config.py` (`build_worker_nodes`, `populate_host_port`). Next.
