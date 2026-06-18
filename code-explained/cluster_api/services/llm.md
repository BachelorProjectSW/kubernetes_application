# `src/cluster_api/services/llm.py` — node selection + the llama call

This is the **last hop before the model**. The cluster API picks one of its worker nodes,
forwards the question to that node's `llama-server` `/completion` endpoint, measures the
queue-vs-inference timing, and returns an `LLMResponse`. It's where the **slot accounting**
(`WorkerNode.active_requests / queued_requests / free_slots`) actually drives a decision.

Three things to hold onto:
1. **The slot model** (defined on `WorkerNode` in `basemodels.py`) — selection is built on it.
2. **The `worker_lock`** — selection + counter updates must be atomic across concurrent
   requests.
3. **The inflight counter is incremented before the call and *always* decremented in
   `finally`** — slots are never leaked.

---

## The slot model (from `models/basemodels.py:57`)

`handle_llm` reasons about each node with four derived quantities. The raw field is
`inflight_requests` (total requests handed to the node); the rest are **computed properties**:

| Property | Definition | Meaning |
|---|---|---|
| `inflight_requests` | raw counter | everything assigned to this node right now |
| `max_slots` | config | how many requests llama can process **in parallel** |
| `active_requests` | `min(inflight, max_slots)` | requests actually being processed |
| `queued_requests` | `max(0, inflight − max_slots)` | overflow waiting for a slot |
| `free_slots` | `max(0, max_slots − active_requests)` | spare capacity |

CLAUDE.md calls this out explicitly: *"reuse them rather than recomputing min/max inline."*
This file is the main consumer.

---

## `round_robin(workers)` (19–40) — the last-resort tiebreaker
```python
33      global rr_index
37      workers = sorted(workers, key=lambda worker: worker.name)
38      worker = workers[rr_index % len(workers)]
39      rr_index += 1
40      return worker
```
- A simple rotating pointer (`rr_index`) over the name-sorted workers. Sorting first makes
  the rotation deterministic regardless of dict/list ordering. Used **only** when every
  candidate is full (see selection step 4). `rr_index` is a module global, so the rotation
  persists across requests.

---

## `choose_worker_node(worker_node_list)` (43–99) — the selection policy

The docstring (46–50) states the policy; the code implements it as a priority cascade:

```python
64      eligible_workers = [w for w in worker_node_list if w.status in {IDLE, WORKING}]
69      if not eligible_workers: return None
73      idle_workers = [w for w in eligible_workers if w.inflight_requests == 0]
77      if idle_workers:
81          return sorted(idle_workers, key=lambda w: w.name)[0]
84      best_free_slots = max(w.free_slots for w in eligible_workers)
86      best_workers = [w for w in eligible_workers if w.free_slots == best_free_slots]
91      if len(best_workers) == 1: return best_workers[0]
95      if best_free_slots > 0: return sorted(best_workers, key=lambda w: w.name)[0]
99      return round_robin(best_workers)
```
- **Eligibility (64–70):** only `IDLE` or `WORKING` nodes. Nodes that are `OFF`,
  `TURNING_ON`, `TURNING_OFF` are excluded, you can't route to a node that isn't up.
- **Step 1 — prefer a fully idle node (73–81).** A node with **zero** inflight requests is
  chosen first (by name, for determinism). The comment (79–80) is the important design link:
  **picking idle nodes by name keeps the *same* nodes busy and leaves the *others* idle, so
  the power scheduler can later turn those idle ones off.** Selection is deliberately
  *concentrating* load, not spreading it, the opposite of classic load balancing, and it's
  on purpose because the goal is energy savings, not even utilization. **Strong point for
  your defense:** cluster selection and node selection both feed the power scheduler.
- **Step 2 — most free slots (84–92).** If no node is fully idle, pick the one with the most
  spare capacity. Single winner → return it.
- **Step 3 — tie on free slots, all with capacity (95–96).** Multiple nodes tie and all have
  `free_slots > 0` → pick the first by name (deterministic).
- **Step 4 — everyone is full (98–99).** If the best `free_slots` is `0` (all candidates
  saturated), fall back to **round-robin** so the overflow is spread fairly rather than
  always piling onto the same node. This is the only time requests get queued behind others.
- Returns `None` only when there are no eligible nodes at all (→ 503 upstream).

---

## `sync_worker_status(worker)` (102–122) — keep status truthful
```python
116     if worker.status in {OFF, TURNING_ON, TURNING_OFF}: return
121     worker.status = IDLE if worker.inflight_requests == 0 else WORKING
122     log_node_status_snapshot(cluster_name, worker)
```
- Recomputes a node's `status` from its inflight count: 0 → `IDLE`, else `WORKING`. **But it
  refuses to touch power-transition states** (116): if a node is mid power-on/off, its status
  is owned by the power scheduler, not by request traffic. This is the boundary between the
  *request* path and the *power* path writing the same field.
- Every change is logged as a `NodeStatusLog` (122) — this is the data that lets you
  reconstruct, after a run, exactly when each node was idle vs working (your power-scheduler
  results).

---

## `handle_llm(question, trace_id)` (125–313) — the main flow

### Select under the lock (173–212)
```python
173     with worker_lock:
174         for worker in config.worker_nodes:
175             sync_worker_status(worker)
177         worker_node = choose_worker_node(config.worker_nodes)
178         if worker_node is None:
185             raise HTTPException(status_code=503, detail="No available worker")
187         worker_node.inflight_requests += 1
188         sync_worker_status(worker_node)
189         inflight_at_selection = worker_node.inflight_requests
...
195         if config.cluster_config.k3d:
196             target_port = worker_node.forwarded_port
197         else:
198             target_port = config.cluster_config.llama_hostport
```
- **The whole select-and-claim is inside `worker_lock`** (173). This is critical: multiple
  requests arrive concurrently (the global API forwards many), and without the lock two could
  both pick the same idle node and both think they got a free slot. The lock makes
  "refresh statuses → choose → increment inflight" **atomic**.
- **Line 174–175** — before choosing, re-sync every node's status from its inflight count, so
  the decision uses current truth.
- **Line 177–185** — choose; if nothing is available, **503 "No available worker."**
- **Line 187 — claim the slot:** increment `inflight_requests` *before* the external call.
  Now the node's `active/queued/free` reflect this request immediately, so a concurrent
  request sees one fewer free slot.
- **Lines 189–193** — snapshot the slot counts *at selection time* (these get returned and
  logged, so the global API's `RequestLog` records how loaded the node was when chosen). This
  is the `inflight_requests_at_selection` etc. on `LLMResponse`.
- **Lines 195–198 — k3d vs production routing.** In the **k3d test harness**, the llama pod
  is port-forwarded to localhost, so the target is `worker_node.forwarded_port`. In
  **production**, it's the node's real IP at `llama_hostport`. This is the
  `ClusterConfig.k3d` flag from CLAUDE.md that keeps the test path working without changing
  production code. (The port is also recomputed at 214–217 for the URL.)

### Call llama (214–244)
```python
214     if config.cluster_config.k3d:
215         url = f"http://localhost:{worker_node.forwarded_port}/completion"
216     else:
217         url = f"http://{worker_node.ip}:{config.cluster_config.llama_hostport}/completion"
219     payload = {"prompt": f"Question: {question.question} Answer:", "n_predict": question.max_output_tokens, "temperature": 0.2}
225     cluster_queue_time_ms = int((time.monotonic() - start_time) * 1000)
226     llama_call_start = time.monotonic()
235     timeout = 180 + (queued_at_selection * 90)
237     response = requests.post(url, json=payload, timeout=timeout)
242     response.raise_for_status()
244     cluster_llama_inference_ms = int((time.monotonic() - llama_call_start) * 1000)
```
- **Lines 219–223 — the actual prompt to the model.** `llama-server`'s `/completion` API:
  the prompt is wrapped as `"Question: ... Answer:"`, `n_predict` caps output tokens (from the
  question config), `temperature=0.2` keeps answers fairly deterministic. This is the only
  place the LLM is actually invoked, the bottom of the whole call stack (Qwen2.5-1.5B per
  your report).
- **The timing split (225, 226, 244) — this is the queue-vs-inference decomposition the
  global API logged.**
  - `cluster_queue_time_ms` (225) = time from entering `handle_llm` to **just before** the
    llama call, i.e. how long selection/locking took (the "queue" portion on the cluster).
  - `cluster_llama_inference_ms` (244) = time **around the llama call itself**, the actual
    model inference.
  - These two are what feed `cluster_queue_time_ms` / `cluster_llama_inference_ms` on the
    `RequestLog`. **This is the exact latency breakdown behind your power-scheduler
    discussion:** the throughput model uses the *inference* number; end-to-end is the global
    API's `global_total_time_ms`. Being able to point at lines 225/244 for "where inference
    latency is measured" is gold for your defense.
- **Line 235 — adaptive timeout:** `180 + queued_at_selection * 90` seconds. Base 180s, plus
  90s for every request already queued ahead of this one on the node. So a backlogged node
  gets a proportionally longer timeout instead of a fixed one, requests don't time out just
  because they're waiting behind others. Slot-aware timeout, a nice detail.

### Build the response (260–272)
```python
262     return LLMResponse(
263         llm_content=result, worker_node=worker_node,
265         inflight_requests_at_selection=inflight_at_selection,
266         active_requests_at_selection=active_at_selection,
267         queued_requests_at_selection=queued_at_selection,
268         max_slots=max_slots_at_selection,
269         cluster_queue_time_ms=cluster_queue_time_ms,
270         cluster_llama_inference_ms=cluster_llama_inference_ms,
271         llama_response_status_code=response.status_code)
```
- Wraps the raw llama JSON plus all the **selection metadata and timings** the global API
  parses (back in `handle_llm_request.py:142`). The `worker_node` is returned in full so the
  global side can log which node served it.

### Error path (274–289) and the slot-release `finally` (291–312)
```python
287     if isinstance(e, HTTPException): raise
289     raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}") from e
291     finally:
293         if worker_node is not None:
294             with worker_lock:
296                 worker_node.inflight_requests = max(0, worker_node.inflight_requests - 1)
297                 sync_worker_status(worker_node)
```
- **Errors (274–289):** a 503 ("no worker") is re-raised as-is; anything else (llama down,
  timeout, bad response) becomes a **502 "LLM request failed."** Both propagate up to the
  global API's inner `except`, which logs the failed `RequestLog` and re-raises a 500 to
  Strato.
- **The `finally` (291–312) is the critical invariant:** **no matter what happens, decrement
  `inflight_requests`** (under the lock, floored at 0) and re-sync status. This is the mirror
  of the increment on line 187. If this didn't run, every failed request would permanently
  "use up" a slot and the node would slowly look full forever (slot leak). The increment-claim
  / finally-release pairing is exactly how you guarantee accurate slot accounting under
  concurrency. **Have this ready:** "how do you avoid leaking slots when a request fails?" →
  this `finally`.

---

## The request, end to end on the cluster

```
handle_llm
  ├ worker_lock:                      ← atomic select+claim
  │    sync all statuses → choose_worker_node → (503 if none)
  │    inflight += 1, snapshot slot counts, pick k3d/prod port
  ├ POST llama /completion (timeout 180 + queued*90)   ← the only LLM call
  │    measure cluster_queue_time_ms (before) + cluster_llama_inference_ms (around)
  ├ build LLMResponse{result, worker, slot snapshot, timings}
  └ finally: worker_lock → inflight -= 1, re-sync   ← never leak a slot
```

## Defense-worthy points
- **Node selection concentrates load on purpose** (idle-first, by name) so other nodes stay
  idle and the power scheduler can turn them off, the link between routing and energy saving.
- **The slot model** (`active/queued/free` as computed properties) is the shared vocabulary;
  reused, not recomputed.
- **`worker_lock` + increment-before / decrement-in-`finally`** is the concurrency-safe slot
  accounting; the `finally` is what prevents leaks on failure.
- **Queue vs inference timing** is measured at lines 225 and 244, this is the latency split
  your power-scheduler uses (inference) vs scoring/end-to-end.
- **k3d vs production port** (`forwarded_port` vs `llama_hostport`) is the test-harness seam.
- **Adaptive timeout** (`180 + queued*90`) scales with backlog.

## Function calls from this file (jump list)
| Call | Defined in | Status |
|------|-----------|--------|
| `config_store.get()` | `util/cluster_config.py` | jump candidate |
| `choose_worker_node`, `round_robin`, `sync_worker_status` | this file | done |
| `log_node_status_snapshot` | `custom_logging/logger.py` | done |
| `requests.post(.../completion)` | **llama-server pod** | bottom of the stack (Kubernetes) |
| `WorkerNode.*` slot properties | `models/basemodels.py` | documented above |

**This is the bottom of the request path** — the next "hop" is the `llama-server` pod itself,
which is external (a llama.cpp server), not our code. So from here the response unwinds back
up: cluster → global (`handle_llm_request.py` parses + logs) → Strato (`_send_request` records
the result). 

**Remaining cluster-side files** (not on the pure request path, but part of the tier):
`util/cluster_config.py` (this cluster's config store + `build_worker_nodes`), and the
**cluster-side `power_scheduler.py`** (the keeper + in-flight-safe shutdown execution, the
local half of your power component). Those pair naturally with the global `power_scheduler.py`
deep-dive.
