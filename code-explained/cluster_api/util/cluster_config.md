# `src/cluster_api/util/cluster_config.py` — this cluster's config + node discovery

This is the cluster API's **own config store** (same role as the global API's
`all_configuration.py`, but a *different class in a different process*). Its big job beyond
"hold the config" is **`build_worker_nodes()`**, which is where the cluster API uses Kubernetes
to **discover its own hardware** at the start of a run. This file is the densest Kubernetes
code in the project, so take it slowly. (Read `kubernetes-primer.md` first.)

It's called from the `/set_config` route (line 85: `config_store.build_worker_nodes()`), which
the global `start_test.py:77` triggers. So the chain is: a test starts → global pushes config
to each cluster → each cluster builds its node list from K8s.

---

## The store: `set` / `get` / `__init__` (10–41, 319)
```python
22      self.config: ClusterInformation | None = None
319 config_store = ConfigStore()
```
- Holds one `ClusterInformation` (this cluster's config + its worker-node list). `set`/`get`
  are trivial. **Note: no lock here** (unlike the global API's `ConfigStore`). The cluster API
  mutates `worker_nodes` from request threads (`llm.py` under `worker_lock`) and the power
  scheduler, the `worker_lock` in `llm.py` guards the *counters*, but this store itself is
  unguarded. Worth flagging as a potential race if config is rebuilt mid-run.
- Line 319 is the shared singleton imported as `config_store`.

---

## `build_worker_nodes()` (43–109) — discover nodes from Kubernetes

This is the important one. It asks K8s "what worker machines are in my cluster?" and builds a
`WorkerNode` for each.

```python
59      if self.config is None: raise Exception("Config is not set yet")
62      self.config.worker_nodes = []
64      api_client = get_api_client()
65      nodes = api_client.list_node()
```
- **Line 64–65** — get a K8s client (the `client_setup.py` factory) and call **`list_node()`**:
  the K8s API for "list every node (machine) in this cluster." Returns node objects with
  metadata, status, labels, addresses.

```python
67      for i, node in enumerate(nodes.items):
68          labels = node.metadata.labels or {}
70          if labels.get("node-role.kubernetes.io/control-plane") == "true":
77              continue
```
- **Lines 67–77 — skip the control plane.** Every K8s node carries **labels**. The control-
  plane node (the "brain", a Pi 5) is labeled `node-role.kubernetes.io/control-plane=true`. We
  skip it because **it doesn't run llama**, only the worker nodes (Jetsons) do. So this loop
  keeps only the machines that can actually serve inference.

```python
79          name = node.metadata.name
80          ip = ""
81          if getattr(node.status, "addresses", None):
82              for address in node.status.addresses:
83                  if address.type == "InternalIP":
84                      ip = address.address
85                      break
86              if not ip:
87                  ip = node.status.addresses[0].address
```
- **Lines 79–87 — extract the node's IP.** A K8s node lists several addresses (internal,
  external, hostname). We prefer the **`InternalIP`** (how to reach it on the cluster network);
  if none is found, fall back to the first address. `getattr(..., None)` guards against the
  field being absent. This IP is later used to reach the node's llama server in production.

```python
89          status = WorkerStatus.OFF
90          if getattr(node.status, "conditions", None):
91              for condition in node.status.conditions:
92                  if condition.type == "Ready":
93                      status = WorkerStatus.IDLE if condition.status == "True" else WorkerStatus.OFF
94                      break
95          worker_node = WorkerNode(name=name, ip=ip, status=status, gpio=0)
101         self.config.worker_nodes.append(worker_node)
```
- **Lines 89–94 — read readiness.** K8s reports node health as **conditions**; the `Ready`
  condition is "is this node healthy and accepting pods?" We map `Ready=True` → `IDLE`
  (available), otherwise `OFF`. So our `WorkerStatus` starts from K8s's own view of the node.
- **Lines 95–101 — build the `WorkerNode`** with name, IP, status, and `gpio=0` as a
  placeholder (assigned next). Append to the list.

```python
103     self.assign_gpios()
104     if self.config.cluster_config.k3d:
105         self.assign_forwarded_ports()
106     else:
107         self.populate_host_port()
108     self.populate_worker_capacities()
109     return self.config.worker_nodes
```
- **Lines 103–108 — the four enrichment steps**, in order:
  1. `assign_gpios()` — map a physical GPIO pin to each node (for power-on control).
  2. **k3d** → `assign_forwarded_ports()` (localhost ports) / **prod** → `populate_host_port()`
     (discover the llama pod's real port). The two-world fork again.
  3. `populate_worker_capacities()` — ask each llama server how many slots it has.
- After this, each `WorkerNode` is fully described: name, IP, status, GPIO, port, and
  `max_slots`. That's the object `llm.py:choose_worker_node` later reasons about.

---

## `assign_gpios()` (111–137) — wire nodes to power pins
```python
123     gpios = self.config.cluster_config.gpio_list
124     if len(gpios) != len(self.config.worker_nodes):
125         raise ValueError("Worker nodes and GPIOs count mismatch: ...")
130     for node, gpio in zip(self.config.worker_nodes, gpios):
131         node.gpio = gpio
```
- The cluster config carries a **`gpio_list`** (one GPIO pin number per worker). This pairs
  each worker with its pin **by list order** (`zip`). The **GPIO pin is how the power scheduler
  physically powers a board on** (a pulse through an optocoupler, covered in the cluster
  `power_scheduler.py`). The strict length check (124) fails fast if the config and the
  discovered hardware disagree, a good integrity guard. **This is the software-to-hardware
  binding**: a `WorkerNode` now knows which physical pin turns it on.

---

## `get_worker_nodes_dict()` (139–153)
- Returns the worker list as plain dicts (`model_dump()`), for JSON HTTP responses. **This
  backs `GET /get_cluster_working_nodes`**, the endpoint `cluster_data.py` polls every scoring
  pass. If `worker_nodes` isn't built yet, it builds first (lazy).

---

## `assign_forwarded_ports()` (155–178) — the k3d path
```python
166     base_port = int(self.config.cluster_config.llama_service_port)
168     workers = sorted(self.config.worker_nodes, key=lambda worker: worker.name)
170     for index, worker in enumerate(workers):
171         worker.forwarded_port = base_port + index
```
- **k3d only.** In tests, each llama pod is exposed on the laptop via `kubectl port-forward` at
  `localhost:<port>`. This assigns each worker a **stable, distinct** local port:
  `base_port + index`, in **sorted name order** so the mapping is deterministic and matches how
  the test harness set up the forwards. This is purely a test-harness convenience; production
  uses real IPs + a discovered hostPort instead.

---

## `populate_host_port()` (180–241) — the production path (lists pods)
```python
193     api_client = get_api_client()
195     pods = api_client.list_namespaced_pod(namespace="default", label_selector="app=llama-server").items
202     for pod in pods:
203         if getattr(pod.status, "phase", None) != "Running": continue
207         conditions = getattr(pod.status, "conditions", None) or []
208         pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)
209         if not pod_ready: continue
213         for container in containers:
214             if container.name != "llama": continue
217             for port in container.ports or []:
218                 if port.host_port is not None: found_ports.add(port.host_port)
231     if len(found_ports) > 1: raise ValueError("Inconsistent llama hostPorts ...")
234     self.config.cluster_config.llama_hostport = found_ports.pop()
```
- **Production only.** It asks K8s for the **llama pods** (`list_namespaced_pod` filtered by the
  label `app=llama-server` in the `default` namespace, this is the labels concept in action),
  and figures out which **hostPort** the llama container is published on.
- It filters to pods that are **Running** (203) **and Ready** (207–209), then looks at the
  container named `llama` (214) and collects its `host_port`s (217–219). A **hostPort** means
  the container's port is exposed directly on the node's IP, so the cluster API can reach the
  model at `node_ip:hostPort`.
- **Robustness logic:** if **no** ready pod exposes a hostPort, it logs a warning and **keeps
  the configured default** (221–229), don't overwrite good config with nothing. If it finds
  **multiple different** hostPorts (231–232), it raises, because the cluster is supposed to be
  uniform and an inconsistency means something's misconfigured. Exactly one found → use it.
- So in production the llama port is **discovered from the live cluster**, not hard-coded.

---

## `populate_worker_capacities()` (243–317) — how many slots each node has
```python
259     for worker in self.config.worker_nodes:
260         if not worker.ip:
261             worker.max_slots = 0; worker.status = WorkerStatus.OFF; continue
266         if self.config.cluster_config.k3d:
267             url = f"http://localhost:{worker.forwarded_port}/props"
268         else:
269             url = f"http://{worker.ip}:{self.config.cluster_config.llama_hostport}/props"
279         response = requests.get(url, timeout=120)
292         worker.max_slots = props.get("total_slots", 0)
293         worker.status = WorkerStatus.IDLE if worker.max_slots > 0 else WorkerStatus.OFF
```
- For each worker, **ask its llama server how many parallel slots it has.** llama.cpp exposes a
  **`/props`** endpoint returning `total_slots` (the number of concurrent requests it can
  process), this becomes `worker.max_slots`, the foundation of the whole slot model in
  `llm.py` (`active/queued/free`).
- The URL forks k3d (localhost forwarded port) vs prod (node IP + discovered hostPort) again.
- **No IP → unusable:** `max_slots = 0`, status `OFF` (260–263).
- **k3d fallback (295–313):** if the probe fails in k3d, default to `max_slots = 1` and `IDLE`,
  because during test bootstrap a pod may still be starting and we don't want the whole run to
  fail. In **production**, a failed probe means `max_slots = 0` / `OFF` (314–316), a node we
  can't probe is treated as unavailable rather than optimistically usable. The asymmetry (test
  is lenient, prod is strict) is deliberate.

---

## Where each `WorkerNode` field comes from (the payoff)

After `build_worker_nodes()`, a `WorkerNode` is fully populated, and now you can say exactly
where each field originates:

| Field | Source |
|---|---|
| `name`, `ip`, initial `status` | K8s `list_node()` (node metadata/addresses/conditions) |
| `gpio` | cluster config `gpio_list`, paired by order |
| `forwarded_port` (k3d) | `assign_forwarded_ports` (`base_port + index`) |
| `llama_hostport` (prod) | `populate_host_port` (discovered from running llama pod) |
| `max_slots` | llama `/props` `total_slots` (`populate_worker_capacities`) |

## Defense-worthy points
- **K8s gives inventory, we schedule.** `build_worker_nodes` uses K8s only to *discover* nodes
  and their state; the actual node *choice* is our `choose_worker_node`.
- **Control-plane nodes are skipped** (they don't run llama).
- **`max_slots` comes from llama's own `/props`** (`total_slots`), it's measured, not guessed.
- **GPIO binding** (`assign_gpios`) is the software→hardware link the power scheduler uses to
  power boards on.
- **k3d vs prod forks** appear three times (ports, hostport discovery, capacity URL); each is
  the test-vs-real-hardware seam.
- **This store has no lock** (unlike the global one), the `worker_lock` in `llm.py` covers
  counter updates, but a config rebuild during a run would be unguarded.
