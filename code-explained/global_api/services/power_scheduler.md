# `src/global_api/services/power_scheduler.py` — the power scheduler's brain

This is the **decision half** of your power-scheduler component: it decides **how many** nodes
should be on, and tells each cluster API to execute (the cluster `power_scheduler.py` does the
GPIO/SSH work). It runs as a **periodic background loop** started in the global `start_test.py`.

This is the single most defense-critical file we've documented, because it contains:
- the **throughput model** (`μ = 1000/inference_ms`, `N_required = ⌈λ/μ⌉`),
- the **latency-feedback model** (`S = L_obs/L_max`, `N_scaled = ⌈N·S⌉`),
- `N_add = max(throughput, latency)`,
- and **issue B** (the code-vs-report latency inconsistency) lives physically at lines
  310–313.

> **Note the typo:** the function is spelled `apply_lantecy_scaling` (should be "latency"). It's
> in the public name, so don't "correct" it when you point at it, that's the actual identifier.

Two framing facts before the line-by-line:
1. **The model is fleet-wide, then distributed.** `current_rps` (λ) and `current_active_nodes`
   are summed across **all clusters**; the throughput model computes a **total** node count for
   the whole fleet; *then* the additions are handed out to clusters in **scoring order**
   (greenest first). This is the coupling to your cluster-selection component.
2. **Turn-on and turn-off use different latency measures.** Turn-on's latency-feedback uses
   **inference** latency; turn-off's SLO guard uses **end-to-end** latency. Know which is which.

---

## Imports (1–18)
```python
7   from .scoring import score_cluster
10  from ...custom_logging.util.log_reader import get_avg_latency, get_sent_logs, get_avg_llama_latency
12  from .cluster_data import get_cluster_runtime_data
15  from ...db.postgres import read_model_logs
```
- **`score_cluster`** (7) — reuses your scoring function to **rank clusters for activation
  order** (not to route a request, to decide *where* to add capacity).
- **The three log readers (10)** are the heart of the signals:
  - `get_avg_llama_latency` → average **inference** latency (used by the throughput model).
  - `get_avg_latency` → average **end-to-end** latency (used by the turn-off SLO guard).
  - `get_sent_logs` → the `LogSent` rows Strato writes per dispatch → used to compute **λ
    (RPS)**.
- **`get_cluster_runtime_data`** (12) + `read_model_logs` (15) — same data-gathering used in
  per-request scoring, reused here.

---

## `_get_simulated_time(config)` (21–38)
- Wraps `compute_simulated_now`; on failure, falls back to real now (with a warning). The
  scheduler needs simulated time because it scores clusters (which need PV/carbon/price at the
  simulated moment), same as the request path.

## `_get_scored_clusters(config, clusters, simulated_time)` (41–95) — rank for activation order
```python
58      now = datetime.now(timezone.utc)
59      start = now - timedelta(seconds=config.latency.latency_window_s)
61      recent_requests = read_model_logs(RequestLog, config.id, since=start)
66      avg_latency_by_cluster = {...}      # same per-cluster averaging as handle_llm_request
73      for cluster in clusters:
74          runtime_data = get_cluster_runtime_data(cluster.cluster_config, simulated_time, config.energy, avg_latency_ms=...)
81          cluster_score = score_cluster(... config.weights.gco2, config.weights.cost, config.weights.latency, runtime_data.avg_latency_ms, config.energy)
93          scored_clusters.append((cluster_score, cluster, runtime_data))
```
- This is **a near-duplicate of the input-gathering in `handle_llm_request`**: read the latency
  window once, average per cluster, build runtime data per cluster, and `score_cluster` each.
  The output is `(score, cluster, runtime_data)` tuples.
- **Why score clusters here at all?** Not to pick one for a request, but to decide **which
  clusters get new nodes first.** Under carbon-first weights, the greenest cluster scores
  highest and therefore gets capacity added first (see `turn_nodes_on`). This is the
  scoring↔power-scheduler coupling, the same scorer drives both routing *and* where capacity
  grows.
- Worth flagging: this duplicates the latency-window/averaging logic from `handle_llm_request`
  rather than sharing it, a DRY smell.

## `get_current_active_nodes(clusters)` (98–115) — N (fleet-wide)
```python
112     if status == WorkerStatus.WORKING or status == WorkerStatus.IDLE:
113         active_nodes_counter += 1
```
- Counts every node across **all clusters** that is `WORKING` or `IDLE` (i.e. powered on and
  usable). This is the `N_active` of the model, and it's **fleet-wide**, not per-cluster.

## `get_current_rps(time_interval_s, config_id)` (118–138) — λ (demand)
```python
135     sent = get_sent_logs(config_id, time_interval_s)
136     count = len(sent) if sent else 0
138     return round(count / time_interval_s, 2)
```
- **λ = (number of requests *sent* in the window) / window seconds.** It counts `LogSent` rows,
  which **Strato writes** at dispatch time (`run_workload.py:115`). So demand is measured at the
  *source* (Strato), not at the global API.
- The docstring (121–122) honestly flags the design question: *should RPS be measured where
  requests are sent (Strato) or where they're received (global)?* They chose sent-side. A fair
  "we debated this" point, sent-side measures *offered* load even if the global API is
  backlogged, which is arguably the right signal for provisioning.

---

## `estimate_required_nodes(avg_llama_latency_ms, current_rps)` (141–174) — the throughput model
```python
159     if current_rps <= 0: return 0
164     if avg_llama_latency_ms <= 0: return 0
171     service_rate_rps = 1000.0 / avg_llama_latency_ms
172     required_nodes = math.ceil(current_rps / service_rate_rps)
173     return required_nodes
```
- **This is `N_required = ⌈λ/μ⌉` from your report.** Two steps:
  - **Line 171 — `μ` (service rate):** `1000.0 / avg_llama_latency_ms`. μ is a **rate** =
    requests-per-second one node can finish = the **reciprocal of the service time**. Service
    time is `avg_llama_latency_ms / 1000` seconds, so μ = 1 / (ms/1000) = **1000/ms**. *That's
    why the 1000 is on top:* it's the ms→s conversion that flips into the numerator because μ
    is a reciprocal. The docstring worked example (147–149): 8000 ms → μ = 1000/8000 = 0.125
    req/s.
  - **Line 172 — `N_required = ⌈λ/μ⌉`:** divide demand by per-node throughput, round **up**
    (you can't have a fraction of a node). Example: λ=1, μ=0.125 → ⌈1/0.125⌉ = **8 nodes**.
- **The latency used is `avg_llama_latency_ms` = INFERENCE latency** (the
  `cluster_llama_inference_ms` measured in `llm.py:244`). **This is correct and consistent with
  the report**, which defines service time as time actively processing, *excluding* waiting. So
  the **throughput term is not the inconsistency** — be precise about that.
- **Guards (159, 164):** no demand or no valid latency → 0 (don't scale). A missing latency
  signal means "I can't estimate," so it abstains rather than guessing.

## `apply_lantecy_scaling(current_active_nodes, avg_latency_ms, max_latency_ms)` (177–217) — the latency-feedback model
```python
199     if max_latency_ms <= 0 or avg_latency_ms <= 0 or current_active_nodes <= 0: return 0
202     if avg_latency_ms > max_latency_ms:
203         scale_factor = avg_latency_ms / max_latency_ms
204         scaled_nodes_needed = int(math.ceil(current_active_nodes * scale_factor))
205         nodes_to_add = scaled_nodes_needed - current_active_nodes
215         return nodes_to_add
217     return 0
```
- **This is `S = L_obs/L_max` (report eq 10) and `N_scaled = ⌈N·S⌉`.** Mapping:
  - `scale_factor` = **S**, `avg_latency_ms` = **L_obs**, `max_latency_ms` = **L_max**.
  - Only fires **when latency exceeds the limit** (202): if `avg > max`, grow the current node
    count by the ratio. Example (docstring 187–188): N=2, avg=16000, max=8000 → S=2 → scaled=4
    → add 2. If latency is under the limit, this term adds **nothing** (217) and the throughput
    model decides.
- **Why this term exists:** the throughput model assumes per-node service rate is constant, but
  under concurrency requests slow each other down. This watches *measured* latency directly as a
  safety signal, if we're over the SLO, add capacity regardless of the throughput estimate.
- **★ ISSUE B lives at the call site, not here.** This function's *parameter* is named
  `avg_latency_ms` (neutral), but in `turn_nodes_on` (lines 310–313) the value passed in is
  **`avg_llama_latency_ms` = inference latency**, while the report's eq 10 defines **L_obs as
  end-to-end** latency. So the code feeds this term *inference* latency, the report says
  *end-to-end*. The function is faithful to whatever it's given; the divergence is **which value
  the caller supplies.** This is the exact thing examiners may probe, and you can now point at
  line 310–313 as the precise location.

## `estimate_nodes_to_add(avg_llama_latency_ms, current_rps, current_active_nodes)` (220–254)
```python
236     required_nodes = estimate_required_nodes(avg_llama_latency_ms, current_rps)
241     if current_active_nodes <= 0:
242         return max(1, required_nodes)
244     nodes_to_add = max(0, required_nodes - current_active_nodes)
```
- Turns "nodes **required**" into "nodes to **add**": subtract what's already on, floor at 0
  (line 244, never negative, scaling *down* is a separate path).
- **Bootstrap case (241–242):** if **nothing** is active, return `max(1, required)`, always turn
  on at least one node so the system can start serving and *begin measuring latency*. Without
  this, a cold cluster with no latency data could never scale up (chicken-and-egg). Good detail.

---

## `turn_nodes_on(config, clusters)` (257–353) — the turn-on orchestration

This assembles the signals, takes the **max**, and distributes additions in scoring order.
```python
269     simulated_time = _get_simulated_time(config)
270     scored_clusters = _get_scored_clusters(config, clusters, simulated_time)
273     sorted_clusters = [cluster for _, cluster, _ in sorted(scored_clusters, key=lambda i: i[0], reverse=True)]
279     avg_llama_latency_ms = get_avg_llama_latency(config.id, config.latency.latency_window_s)
280     current_active_nodes = get_current_active_nodes(clusters)
281     current_rps = get_current_rps(config.latency.latency_window_s, config.id)
289     if current_rps <= 0: return
295     if avg_llama_latency_ms <= 0: return
303     nodes_to_add = estimate_nodes_to_add(avg_llama_latency_ms, current_rps, current_active_nodes)
310     latency_scaling_nodes = apply_lantecy_scaling(current_active_nodes, avg_llama_latency_ms, config.latency.max_ms)
316     nodes_to_add = max(nodes_to_add, latency_scaling_nodes)
```
- **Lines 270–276 — rank clusters** by score, highest first. This `sorted_clusters` list is the
  order capacity will be added in.
- **Lines 279–281 — read the three signals:** inference latency (μ input), fleet active count
  (N), and RPS (λ).
- **Lines 289–300 — abstain guards:** no demand or no latency reading → do nothing this cycle.
- **Line 303 — throughput estimate** `N_throughput`.
- **Lines 310–313 — latency estimate** `N_latency`. **← this is the call that feeds inference
  latency into the `S` term (issue B).**
- **Line 316 — `N_add = max(N_throughput, N_latency)`.** **Max, not sum**, on purpose: the two
  estimate the *same quantity* (total nodes needed) from different assumptions; summing would
  double-count and over-provision, max covers whichever constraint binds. This is the slide
  point.
```python
318     for cluster in sorted_clusters:
319         if nodes_to_add <= 0: break
322         for worker_node in cluster.worker_nodes:
323             if worker_node.status == WorkerStatus.OFF: powered_off_nodes += 1
326         amount = min(nodes_to_add, powered_off_nodes)
333         url = f"http://{cluster.cluster_config.ip}:{cluster.cluster_config.port}/turn_on_nodes/"
334         response = requests.post(url, params={"number_of_nodes": amount}, timeout=500)
337         turned_on = payload.get("node_changed", amount)
338         nodes_to_add -= turned_on
```
- **The distribution loop (318–352).** Walk clusters **greenest-first**; for each, power on
  `min(remaining_to_add, its_OFF_nodes)`; subtract what actually turned on; stop when the budget
  is spent. So under carbon-first weights, capacity grows on the cleanest cluster until it's
  full, then spills to the next. **This is the literal coupling: the power scheduler adds nodes
  in cluster-selection's ranking order.**
- **Line 333–334 — calls the cluster API's `/turn_on_nodes`** (the endpoint backed by the
  cluster `power_scheduler.change_node_status`, the GPIO pulses). It uses `node_changed` from the
  response (337) to decrement by what *actually* powered on, not just what was requested,
  robust to partial success.

---

## `turn_off_idle_nodes(config)` (355–396) — the turn-off pass (the SLO guard)
```python
365     avg_latency_ms = get_avg_latency(config.id, config.latency.latency_window_s)
366     if avg_latency_ms > config.latency.max_ms:
372         return
374     for cluster in config.clusters:
377         url = f"http://{cluster.ip}:{cluster.port}/turn_off_idle_nodes/"
378         idle_time = config.power_scheduler.idle_time_for_turn_off_s
384         response = requests.post(url, params={"idle_time": idle_time}, timeout=500)
```
- **Lines 365–372 — the global SLO guard.** Before turning *anything* off, check the cluster's
  **average end-to-end latency**; if it's above the SLO (`max_ms`), **skip the entire turn-off
  pass**. Rationale: a node can *look* idle (e.g. just powered on, no traffic yet) while the
  system is actually overloaded, you must not shed capacity while you're slow. This is the
  per-cluster latency guard you discussed; it's distinct from the per-node idle threshold the
  cluster API enforces.
- **★ Note the latency measure here is `get_avg_latency` = END-TO-END**, whereas turn-on's
  `S` term used `get_avg_llama_latency` = inference. So **turn-down is gated on end-to-end
  latency, turn-up's safety term on inference latency.** This asymmetry is real, have a stance:
  end-to-end is the right thing for "are users hurting?" (turn-off safety), while inference is
  the right thing for "how fast can a node clear work?" (throughput), arguably each uses the
  *appropriate* measure, but it's inconsistent with eq 10's single `L_obs` definition.
- **Lines 374–388 — delegate per cluster:** POST `/turn_off_idle_nodes` with the idle threshold.
  The actual per-node decisions (keeper, in-flight check, idle age) happen **cluster-side** (the
  file we already documented). The global side only decides *whether to run the pass at all*.

---

## `power_scheduler_loop()` (399–428) — the background loop
```python
407     while True:
409         config = config_store.get()
410         if config is None: break
415         timeout = config.power_scheduler.timeout_s
417         await asyncio.sleep(timeout)
420         latest_config = config_store.get()
421         if latest_config is None or not latest_config.power_scheduler.start: break
425         all_clusters = config_store.get_cluster_information()
426         turn_nodes_on(latest_config, all_clusters)
427         turn_off_idle_nodes(latest_config)
428     log.info("global_api.power.scheduler_ended")
```
- An **async loop** (started as a thread running `asyncio.run` in `start_test.py`). Each cycle:
  1. **sleep first** (`timeout_s`), so the first scaling happens one interval *after* the test
     starts (gives the system time to generate latency/RPS data before deciding).
  2. **re-read the config** (420) and **break if `power_scheduler.start` is False** (421). This
     is the **stop coupling**: `stop_test` → `config_store.stop_power_scheduler()` sets
     `start=False`, and the loop notices here and exits. (Re-reading also picks up a cleared
     config.)
  3. **turn on, then turn off** (426–427), using fresh cluster info from
     `config_store.get_cluster_information()` (which live-queries each cluster).
- Order matters: **scale up before scaling down** each cycle, so a burst is met with capacity
  before any idle trimming is considered.

---

## The whole component in one picture

```
power_scheduler_loop (every timeout_s):
  ├ turn_nodes_on:
  │    score+rank clusters (greenest first)            ← coupling to scoring
  │    λ = get_current_rps (LogSent count / window)
  │    μ = 1000 / avg_llama_latency_ms  (INFERENCE)    ← throughput, report-consistent
  │    N_throughput = ⌈λ/μ⌉ − N_active   (fleet-wide)
  │    N_latency    = ⌈N_active·(L_obs/L_max)⌉ − N_active,  L_obs = INFERENCE ★issue B (report says end-to-end)
  │    N_add = max(N_throughput, N_latency)            ← max, not sum
  │    distribute N_add to clusters greenest-first → POST /turn_on_nodes (GPIO)
  └ turn_off_idle_nodes:
       if avg END-TO-END latency > SLO: skip whole pass ← global guard
       else POST /turn_off_idle_nodes per cluster → cluster does keeper + in-flight + idle-age
```

## Defense-worthy points (this file IS your second component)
- **`μ = 1000/inference_ms`**: μ is a rate = reciprocal of service time; the 1000 is ms→s that
  ends up on top because of the reciprocal. `N_required = ⌈λ/μ⌉`. Throughput uses **inference**
  latency, **consistent with the report's service-time definition.**
- **`S = L_obs/L_max`** is eq 10, implemented as `scale_factor = avg_latency_ms/max_latency_ms`
  in `apply_lantecy_scaling` (203). **Issue B**: the value fed in (lines 310–313) is *inference*
  latency, but eq 10 defines `L_obs` end-to-end. Point at the call site.
- **`N_add = max(throughput, latency)`** — same quantity from two assumptions; max avoids
  double-counting.
- **Fleet-wide estimate, scoring-order distribution** — capacity grows on the greenest cluster
  first; this is the scoring↔power coupling you close your talk on.
- **Turn-off is gated on end-to-end latency** (SLO guard), turn-up's safety term on inference,
  the asymmetry to have a stance on.
- **Bootstrap `max(1, required)`** solves the cold-start chicken-and-egg.
- **Stop coupling**: the loop exits when `power_scheduler.start` goes False (set by `stop_test`).
- **This file has no unit tests** (see `assessment.md`), it's validated only via the k3d
  integration scenarios. If asked for a unit test, the obvious one is
  `estimate_required_nodes(8000, 1) == 8`, trivial precisely *because* these are nearly-pure
  functions; extracting them fully would make the whole component unit-testable.

## Function calls / jumps
| Call | Defined in | Status |
|------|-----------|--------|
| `get_avg_llama_latency`, `get_avg_latency`, `get_sent_logs` | `custom_logging/util/log_reader.py` | small jump (the latency readers) |
| `score_cluster`, `get_cluster_runtime_data`, `read_model_logs` | scoring / cluster_data / postgres | done |
| `config_store.get/get_cluster_information/stop` | `util/all_configuration.py` | done |
| `requests.post(/turn_on_nodes, /turn_off_idle_nodes)` | **cluster_api** `power_scheduler.py` | done (the executor) |

**Natural small follow-up:** `custom_logging/util/log_reader.py` — the three reader functions
(`get_avg_llama_latency` vs `get_avg_latency` vs `get_sent_logs`) that define **exactly** which
latency is inference vs end-to-end. That file is where issue B is ultimately grounded, and it's
short.
