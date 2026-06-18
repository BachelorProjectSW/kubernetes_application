# `src/cluster_api/services/cancel_all_llama_pods.py` — restart the model pods

Small file, but it's a clean example of the **"shell out to `kubectl`"** style of talking to
Kubernetes (as opposed to the Python client used in `cluster_config.py`). Backs the
`POST /cancel_all_llama_pods` endpoint, a manual "restart the models cleanly" affordance.

```python
3   from .power_scheduler import run_cmd
8   def cancel_all_llama_pods():
26      try:
27          stdout = run_cmd("sudo kubectl delete pods -l app=llama-server")
28          log.info("cluster.llama_pods_deleted", stdout=stdout.strip())
29      except Exception as e:
30          log.error("cluster.llama_pods_delete_failed", error=str(e))
```

- **Line 3** — imports `run_cmd` from the cluster `power_scheduler.py`. `run_cmd` is the helper
  that **runs a shell command from Python** (a `subprocess` wrapper) and returns its stdout.
  We'll document it fully in the power-scheduler deep-dive; for now: it's how Python executes a
  CLI tool.
- **Line 27 — the actual K8s action.** `kubectl delete pods -l app=llama-server` tells
  Kubernetes "delete every pod **labeled** `app=llama-server`", i.e. all the llama pods across
  the cluster. The `-l` is a **label selector** (same labels concept as
  `list_namespaced_pod(label_selector=...)`, just via the CLI). `sudo` because the cluster API
  needs elevated rights to run `kubectl` on the node.
- **Why deleting is safe (the key K8s idea):** the llama server is deployed as a **DaemonSet**
  (one pod per worker, see the primer). When you delete a DaemonSet's pods, **Kubernetes
  automatically recreates them.** So "delete all llama pods" is really "restart all llama
  servers cleanly", K8s self-heals back to one fresh pod per node. The docstring (12–15) says
  exactly this. This is the whole point: you don't manually restart anything; you delete and
  let the DaemonSet reconcile.
- **Lines 29–30 — fail-soft:** any error is logged, not raised. The endpoint returns its
  "restarting" message regardless. It's a maintenance action, a failure shouldn't crash
  anything.

## Why it exists
Long runs can leave a llama server in a bad state (stuck slots, memory growth). Rather than SSH
into each node, this one call wipes and lets K8s rebuild them all. It's the "turn it off and on
again" button for the models.

## Defense-worthy points
- **Two K8s styles in this codebase:** Python client (`cluster_config.py`, for *reading*) vs
  `kubectl` via `run_cmd` (here, for a blunt *action*). This file is the canonical example of
  the second.
- **DaemonSet self-healing** is what makes "delete all pods" a *restart*, not a destruction.
- **`-l app=llama-server`** is a label selector; the same label the Python client filters on in
  `populate_host_port`.
- **`run_cmd`** (subprocess) is the bridge from Python to shell, shared with the power
  scheduler; documented there.

**Note:** `run_cmd` lives in the cluster `power_scheduler.py`, which is the next natural file,
it's both your *power-scheduler component* (cluster half) and the home of the GPIO/SSH/`kubectl`
hardware-control code you're least familiar with.
