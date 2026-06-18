# `src/cluster_api/services/power_scheduler.py` — the hardware half of the power scheduler

This is the **cluster-local power scheduler**: the code that *physically* powers boards on and
off, and the keeper / in-flight safety logic you present. The **global** power scheduler
*decides how many* nodes a cluster should have; **this file executes** those decisions on real
hardware. It's the file you said you're least familiar with, and it's where the project touches
the physical world (GPIO pins, SSH, Kubernetes pods).

Two physical actions to anchor on:
- **Power ON** = send a short electrical **pulse on a GPIO pin** (through an optocoupler wired
  to the board's power button). `turn_on_node`.
- **Power OFF** = **SSH into the node and run `sudo shutdown`**. `turn_off_node`.

Everything else is orchestration and safety around those two.

---

## `run_cmd(cmd)` (18–34) — run a shell command from Python
```python
28      result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
34      return result.stdout
```
- The bridge from Python to the shell. `subprocess.run` launches a command as a child process.
  - `shell=True` — run the string through the shell (so `gpioset ...` / `kubectl ...` work as
    written). (`shell=True` with untrusted input is an injection risk; here the commands are
    built from our own config, so it's safe, but worth knowing.)
  - `capture_output=True, text=True` — capture stdout/stderr as strings.
- Returns just stdout. **Note it does not check the exit code** (no `check=True`), so a failed
  command returns empty/partial output rather than raising. Callers don't currently inspect
  failure here. This is the helper `cancel_all_llama_pods` and `turn_on_node` use to run CLI
  tools.

---

## `turn_on_node(worker, cluster_name)` (37–75) — the GPIO power-on pulse
```python
56      run_cmd(f"gpioset gpiochip4 {gpio}=1")
57      time.sleep(0.5)
58      run_cmd(f"gpioset gpiochip4 {gpio}=0")
65      worker_node.status = WorkerStatus.TURNING_ON
66      log_node_status_snapshot(cluster_name, worker_node)
```
- **GPIO** (General Purpose Input/Output) pins are the physical pins on the control board. Each
  worker has a GPIO pin assigned (the `gpio` field set by `assign_gpios` in `cluster_config.py`)
  that's wired, through an **optocoupler**, to that worker's power button.
- **Lines 56–58 — the pulse:** `gpioset gpiochip4 {gpio}=1` drives the pin **high** (button
  "pressed"), wait **0.5s**, then `=0` drives it **low** (button "released"). That momentary
  high-low is electrically the same as a human briefly pressing the power button. `gpiochip4`
  is the specific GPIO controller chip on the board. `gpioset` is the Linux CLI for setting GPIO
  lines (run via `run_cmd`).
- **The optocoupler** (from your report) electrically isolates the control board from the
  worker's power circuitry, so the pulse triggers the button without directly wiring the two
  boards' electronics together. Safety + isolation.
- **Line 65** — mark the node `TURNING_ON` (not yet `IDLE`; it has to boot and start its llama
  pod first, that's what `wait_for_nodes_to_be_ready` confirms). Logged as a `NodeStatusLog`.
- Failure → warn and return `False` (68–75). Powering on is best-effort; a failure is logged,
  not fatal.

---

## `turn_off_node(worker, cluster_name)` (78–151) — SSH shutdown, with a safety re-check
```python
91      worker_node.status = WorkerStatus.TURNING_OFF
93      time.sleep(10)
95      if worker_node.inflight_requests > 0:
96          worker_node.status = WorkerStatus.IDLE
104         return False
106     client = paramiko.SSHClient()
107     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
109     client.connect(hostname=worker_node.ip, username=worker_node.name, password=worker_node.name)
116     command = "sudo -S shutdown now"
118     stdin, stdout, stderr = client.exec_command(command)
121     stdin.write(worker_node.name + "\n")
138     time.sleep(20)
139     worker_node.status = WorkerStatus.OFF
```
- **Lines 91–104 — the in-flight safety re-check (one of your two key guards).** It marks the
  node `TURNING_OFF`, then **waits 10 seconds** and **re-checks `inflight_requests`**. If any
  request arrived in that window, it **aborts**: revert to `IDLE` and return `False`. This is
  the race protection, between "decided to turn off" and "actually shut down," a request could
  land; the 10s pause + re-check catches that so you never kill a node mid-request. This is the
  cluster-side counterpart to the *global* scheduler's latency guard; together they implement
  "never power off a node with in-flight requests."
- **Lines 106–113 — SSH connection via `paramiko`** (a pure-Python SSH client). It connects to
  the worker at `worker_node.ip`. **`AutoAddPolicy`** (107) auto-accepts the host's SSH key
  rather than prompting, fine on a trusted private network, but it disables host-key
  verification (a security trade-off worth flagging).
- **Security smell to acknowledge:** `username=worker_node.name, password=worker_node.name`
  (line 109) and the password sent to sudo on line 121, the node's **username and password are
  both just the node's name**. Acceptable only because this is an isolated lab network; you
  should be ready to say "credentials are trivial because the cluster is air-gapped on
  Tailscale, not production-hardened."
- **Lines 116–122 — `sudo -S shutdown now`.** `shutdown now` halts the machine. `sudo -S` makes
  sudo **read the password from stdin**, which is why line 121 writes the password (the node
  name) into stdin. That's how a non-interactive SSH session supplies a sudo password.
- **Lines 136–141** — close SSH, **wait 20s** to let the box actually power down, then mark
  `OFF`. The sleeps (10s before, 20s after) make this a slow, deliberate operation, hence why
  power-off is done sequentially while power-on is parallelized (below).
- Failure → revert to `IDLE`, warn, return `False` (142–151). A failed shutdown leaves the node
  usable rather than stuck in a transition state.

---

## `check_if_llama_pod_is_ready(worker, api_client, ...)` (154–199) — K8s readiness
```python
173     pods = api_client.list_namespaced_pod(
175         field_selector=f"spec.nodeName={worker_node.name}",
176         label_selector="app=llama-server").items
180     if getattr(pod.status, "phase", None) != "Running": continue
185     pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)
187     if pod_ready: return True
```
- After a node boots, its llama pod still has to start. This asks Kubernetes: "is there a
  **running + ready** llama pod **on this specific node**?" The **`field_selector=
  spec.nodeName=<node>`** narrows to pods scheduled on that node; the **`label_selector=
  app=llama-server`** narrows to llama pods. `phase == "Running"` + the `Ready` condition (which
  reflects llama's **readiness probe**, so the model is actually up, not just the container) =
  ready. This is the K8s-side confirmation that complements the GPIO power-on.

---

## `refresh_worker_capacity(worker, cluster_config)` (202–253) — re-probe `/props`
- Same `/props` → `total_slots` probe as `populate_worker_capacities` in `cluster_config.py`,
  but used **after a node powers back on** to re-read its slot count and flip it to `IDLE` once
  capacity > 0. k3d vs prod URL fork again. So a freshly-powered node gets its `max_slots`
  refreshed before it's considered available.

---

## `wait_for_nodes_to_be_ready(nodes, ...)` (256–313) — the post-power-on poll loop
```python
274     deadline = time.time() + timeout_s            # default 300s
278     while time.time() < deadline:
282         pod_ready = check_if_llama_pod_is_ready(node, api_client, cluster_name)
287         if node.max_slots > 0: ready_nodes.append(node); continue
291         capacity_ready = refresh_worker_capacity(node, cluster_config)
296     for node in ready_nodes:
298         if node.status not in {IDLE, WORKING}: node.status = IDLE
301     if len(ready_nodes) == len(worker_nodes): return True
304     time.sleep(poll_interval_s)
306     for node in worker_nodes:                     # timed out
307         if node.status not in {IDLE, WORKING}: node.status = OFF; node.max_slots = 0
313     return False
```
- After powering nodes on, you can't use them until **both** their **llama pod is ready** *and*
  their **capacity is known**. This polls (every 2s, up to 300s) until every requested node
  satisfies both, then flips them to `IDLE` and returns `True`.
- **Two-gate readiness:** pod ready (K8s) **and** `max_slots > 0` (llama `/props`). A node that
  booted but whose model isn't serving yet isn't counted.
- **Timeout handling (306–311):** any node still not ready by the deadline is forced to `OFF`
  with `max_slots = 0`, so a node that failed to come up is treated as unavailable, not left in
  a limbo `TURNING_ON` state. Fail-safe.

---

## `change_node_status(number_of_nodes, status)` (316–363) — the on/off entry point
This is what the **`/turn_on_nodes` and `/turn_off_nodes` endpoints** call (and thus what the
**global power scheduler** ultimately drives).
```python
335     if status == "on":
336         nodes_to_change = select_nodes_to_turn_on(number_of_nodes, nodes)
337         with ThreadPoolExecutor(max_workers=max(1, len(nodes_to_change))) as executor:
338             futures = [executor.submit(turn_on_node, node, cluster_name) for node in nodes_to_change]
340                 future.result()
342         ready = wait_for_nodes_to_be_ready(nodes_to_change, cluster_name)
351     elif status == "off":
352         nodes_to_change = select_nodes_to_turn_off(number_of_nodes, nodes)
353         for node in nodes_to_change:
354             turn_off_node(node, ...)
```
- **Turn ON (335–349) — parallel.** Picks which OFF nodes to power on, then powers them on
  **concurrently** using a `ThreadPoolExecutor` (one thread per node). The docstring explains
  why: a single power-on takes several seconds (boot + pod start), so doing N nodes
  sequentially would be N×slow; threads start them all at once. `future.result()` (340) waits
  for each pulse to finish, then `wait_for_nodes_to_be_ready` blocks until they're actually
  serving. **This is a third concurrency mechanism in the codebase**, after threads
  (`start_test`) and asyncio (`run_workload`), a `ThreadPoolExecutor` here, used because the
  power-on work is slow I/O (sleeps, network, K8s) that parallelizes well.
- **Turn OFF (351–354) — sequential.** Powers off the selected idle nodes one at a time (each
  `turn_off_node` has its own 10s + 20s sleeps and the in-flight re-check). Not parallelized,
  shutdown is slower and less urgent than scaling up.
- Returns a summary dict (358–363) of what changed.

---

## `select_nodes_to_turn_on` (366–385) / `select_nodes_to_turn_off` (388–405)
- Simple pickers, **in list order**, capped at `number_of_nodes`:
  - turn-on: the first N nodes whose status is `OFF`.
  - turn-off: the first N nodes whose status is `IDLE`.
- Note: these iterate `worker_nodes` in **config order** (not sorted), whereas the keeper logic
  below sorts by name. A subtle inconsistency, on-selection uses raw order, the keeper guard
  uses sorted order.

---

## `get_idle_time(node_name, cluster_name)` (408–444) — how long has it been idle?
```python
428     entry = get_worker_nodes_logs(config_id, cluster_name, node_name)
433     if entry is None: return 0
439     if str(entry.status).lower() == WorkerStatus.IDLE.value:
441         return (now - entry.timestamp).total_seconds()
444     return 0
```
- Reads the **latest `NodeStatusLog`** for the node (from the DB, via `get_worker_nodes_logs`).
  If that latest status is `IDLE`, returns **how many seconds ago** it became idle; otherwise
  returns `0` (so a non-idle node is never treated as eligible to shut down).
- So "idle time" is reconstructed from the status-log history, the same `NodeStatusLog` rows
  that `sync_worker_status` and the power transitions write. **Conservative default:** missing
  log or not-idle → `0` → won't be turned off.

---

## `turn_off_idle_nodes(idle_time, stay_one)` (447–517) — the idle-shutdown policy

This is the cluster-side turn-off pass (called by `/turn_off_idle_nodes`, driven by the global
scheduler). It's where the **keeper** lives.
```python
472     nodes = sorted(config.worker_nodes, key=lambda n: n.name)
473     keeper = nodes[0]
475     for node in nodes:
476         if node is keeper: continue
479         if node.status != WorkerStatus.IDLE: continue
489         if node.inflight_requests > 0: continue
498         last_request = get_idle_time(node.name, cluster_name)
500         if last_request > idle_time:
508             turn_off_node(node, cluster_name)
```
- **Lines 472–473 — the keeper (your "always keep one node on" invariant).** Sort nodes by
  name, and the **first one is the keeper**, permanently skipped (476). Because it's chosen by
  sorted name, it's **always the same node**, deterministic. This is what guarantees a cluster
  never goes fully dark, so cluster selection always has a target and the cluster can't drop
  out of contention by accident. **This is the exact "keeper" you reference in your slides; it's
  enforced right here, lines 472–476.**
- **The eligibility gauntlet** each non-keeper node must pass to be shut down:
  1. **must be `IDLE`** (479) — not working, not transitioning.
  2. **zero in-flight requests** (489) — the second of your guards, "never power off a node
     with in-flight requests," enforced here *and* re-checked inside `turn_off_node` (the
     belt-and-braces double check).
  3. **idle longer than the threshold** (500) — `get_idle_time > idle_time`. Only then
     `turn_off_node`.
- Each failed check just `continue`s (with a debug log explaining why), so you can trace
  exactly why a node was or wasn't shut down.
- **Note:** the `stay_one` parameter is in the signature but **not actually used** in the body,
  the keeper logic (always skip `nodes[0]`) already guarantees one stays on, so `stay_one` is
  effectively dead/legacy here. Good "is everything up to date?" example: the route passes
  `stay_one=True`, but this function ignores it and relies on the keeper instead.

---

## How the two power-scheduler halves fit together

```
GLOBAL power_scheduler (decides counts)            CLUSTER power_scheduler (this file, executes)
  turn-on:  POST /turn_on_nodes (N)        ──────►  change_node_status(N,"on")
                                                       select OFF nodes → ThreadPool: turn_on_node (GPIO pulse)
                                                       → wait_for_nodes_to_be_ready (pod + /props)
  turn-off: POST /turn_off_idle_nodes ─────────────► turn_off_idle_nodes(idle_time)
                                                       keeper skipped; per node: IDLE? no inflight? idle>thresh?
                                                       → turn_off_node (10s re-check → SSH sudo shutdown → 20s)
```

## Defense-worthy points (this file is dense with them)
- **Power ON = GPIO pulse** (`gpioset gpiochip4 <pin>=1`, 0.5s, `=0`) through an **optocoupler**
  to the power button. `turn_on_node`.
- **Power OFF = SSH `sudo -S shutdown now`** via paramiko. `turn_off_node`.
- **Two in-flight guards:** `turn_off_idle_nodes` filters `inflight_requests > 0`, *and*
  `turn_off_node` waits 10s and re-checks before shutting down. The keeper invariant
  (`nodes[0]` by sorted name) guarantees one node always stays on, this is your "keeper" and
  "never kill a busy node," and you can now point at lines 472–476, 489, and 95–104.
- **Power-on is parallel (`ThreadPoolExecutor`), power-off is sequential** (third concurrency
  mechanism in the system).
- **Readiness is two-gated:** K8s pod Ready *and* llama `/props` capacity > 0.
- **Stale code to flag:** `stay_one` is accepted but unused (keeper supersedes it); on-selection
  uses raw config order while the keeper uses sorted order.
- **Security trade-offs to own:** SSH `AutoAddPolicy` (no host-key check) and username=password=
  node name, acceptable only because the cluster is isolated on Tailscale.

## Function calls / jumps from this file
| Call | Defined in | Status |
|------|-----------|--------|
| `run_cmd` → `subprocess` / `gpioset` / `kubectl` | this file / OS | done |
| `paramiko.SSHClient` | library (SSH) | external |
| `get_api_client`, `list_namespaced_pod` | `client_setup.py` / K8s | done |
| `refresh_worker_capacity` → llama `/props` | this file / llama pod | done |
| `get_worker_nodes_logs` | `custom_logging/util/log_reader.py` | small jump |
| `log_node_status_snapshot` | `custom_logging/logger.py` | done |

**Next natural step:** the **global** `power_scheduler.py`, the *decision* half (throughput
model `μ = 1000/inference_ms`, latency feedback `S = L_obs/L_max`, the loop started in
`start_test.py`). This file is the executor; that one is the brain, and together they are your
complete power-scheduler component.
