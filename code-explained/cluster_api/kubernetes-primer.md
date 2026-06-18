# Kubernetes primer — what it is and how *this project* uses it

You said you don't understand Kubernetes (K8s) or how we use it. This doc is the background
you need to read the cluster-API code. It's not a copy of any one file; it's the mental model,
then a map of exactly where K8s shows up in our code.

---

## 1. What Kubernetes is, in plain terms

Kubernetes is a system for **running and managing containers across a group of machines**. A
few core ideas, each with the one-sentence version you actually need here:

- **Node** — a physical/virtual machine that's part of the cluster. In our project a node is a
  **Raspberry Pi or Jetson** board. There are two kinds:
  - **control-plane node** — the "brain" that schedules work and holds cluster state (runs on
    a Raspberry Pi 5 in our setup). It does **not** run our LLM.
  - **worker node** — where actual workloads run (the Jetsons running `llama-server`).
- **Pod** — the smallest unit K8s runs: one (or a few) containers together. Our `llama-server`
  runs **inside a pod** on each worker node. "Forwarding the question to the node's llama
  server" really means "to the llama pod on that node."
- **Container** — a packaged process (here, the llama.cpp server). A pod wraps one or more
  containers.
- **Label** — a key/value tag stuck on K8s objects so you can select them, e.g. every llama
  pod has the label `app=llama-server`. We constantly query "give me everything labeled
  `app=llama-server`."
- **DaemonSet** — a rule that says "run exactly one copy of this pod on **every** worker
  node." Our llama server is deployed as a DaemonSet, so each worker automatically gets one
  llama pod, and if you delete a pod, K8s **recreates** it. (That's why
  `cancel_all_llama_pods` can just delete them all, the DaemonSet brings them back.)
- **K3s / k3d** — K3s is a lightweight Kubernetes distribution made for small hardware (the
  Pis). **k3d** runs K3s clusters inside Docker on your laptop, used by our test harness to
  fake the Pi clusters. Same K8s API, different hardware underneath. This is why the code has
  the `k3d` flag everywhere.
- **kubeconfig** — a credentials file that tells a K8s client *which* cluster to talk to and
  how to authenticate. Needed when our code runs **outside** the cluster (local dev).
- **`kubectl`** — the command-line tool for talking to a cluster (`kubectl get pods`,
  `kubectl delete pods ...`). We use it directly in one place.

## 2. Two ways our code talks to Kubernetes

Our cluster API talks to K8s in **two different styles**, and it helps to know which is which:

1. **The Python client library** (`from kubernetes import client, config`). This is the
   "proper" programmatic API: `api_client.list_node()`, `api_client.list_namespaced_pod(...)`.
   Used to **discover** nodes and pods and read their properties. Lives in
   `util/client_setup.py` and `util/cluster_config.py`.
2. **Shelling out to `kubectl`** via `run_cmd(...)` (a subprocess call). Used for blunt
   actions like `kubectl delete pods -l app=llama-server`. Lives in
   `cancel_all_llama_pods.py` and the cluster `power_scheduler.py`. This is the less elegant
   path (running a CLI from Python and parsing text), but it's simple.

## 3. Where the cluster API authenticates: in-cluster vs local

A K8s client needs credentials. Our `get_api_client()` (`util/client_setup.py`) handles
**both** environments automatically:

- **In production**, the cluster API runs *as a pod inside its own cluster*. K8s injects
  credentials into every pod, so `config.load_incluster_config()` just works, the pod can
  query its own cluster with no extra setup.
- **In local/k3d dev**, the code runs as a normal process *outside* any cluster, so there are
  no injected credentials. It falls back to `KUBECONFIG` (a path to a kubeconfig file).

This try-in-cluster-then-fall-back-to-kubeconfig pattern is the standard way to write K8s code
that runs both inside and outside a cluster without changes.

## 4. The full picture: what the cluster API actually uses K8s *for*

Putting it together, here's the cluster API's relationship with Kubernetes during a run:

```
/set_config arrives (from global start_test)
   └─ config_store.build_worker_nodes()
        ├─ get_api_client()                ← authenticate to K8s
        ├─ api_client.list_node()          ← "what machines are in my cluster?"
        │     skip control-plane, keep workers, read each node's IP + Ready state
        ├─ assign_gpios()                  ← map a GPIO pin to each worker (for power control)
        ├─ assign_forwarded_ports() [k3d]  OR  populate_host_port() [prod, lists llama pods]
        └─ populate_worker_capacities()    ← ask each llama /props for its slot count
```

So K8s is used by the cluster API to **discover its own hardware**: which worker nodes exist,
their IPs, whether they're Ready, and (in prod) which port the llama pod is on. It does **not**
use K8s to *schedule* the LLM work, that's our own `choose_worker_node` logic. K8s gives us
the inventory; we make the scheduling decisions on top of it.

The *other* K8s use is **power control and pod lifecycle**: deleting/restarting llama pods
(`cancel_all_llama_pods`) and, in the power scheduler, physically powering boards on (GPIO) and
shutting them down (SSH). Those are covered in their own docs.

## 5. The simulated-vs-real hardware seam (why `k3d` is everywhere)

- **Real deployment**: nodes are Pis/Jetsons; the llama pod is reached at the worker's real IP
  on a `hostPort` discovered from the running pod (`populate_host_port`). Power control is real
  (GPIO pulses, SSH shutdown).
- **k3d test harness**: nodes are Docker containers; the llama pod is reached on
  `localhost:<forwarded_port>` set up by `kubectl port-forward` (`assign_forwarded_ports`).
  Capacities fall back to a default if a pod is still starting.

Every `if config.cluster_config.k3d:` branch in the code is choosing between these two worlds.
When you read the cluster API, mentally tag each K8s call as "this is discovering/► acting on
real hardware (prod)" or "this is the Docker-faked version (k3d)."

---

### TL;DR for your defense
- K8s runs our `llama-server` as **one pod per worker node** (a DaemonSet on K3s).
- The cluster API uses the **K8s API to discover nodes/pods** (inventory), then applies **our
  own** `choose_worker_node` logic to schedule, K8s does not pick the node.
- It authenticates **in-cluster in prod, via KUBECONFIG locally** (`get_api_client`).
- `k3d` is K3s-in-Docker for tests; every `k3d` branch swaps real hardware for the faked
  local version.
