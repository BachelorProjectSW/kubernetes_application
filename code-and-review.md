# Code Breakdown & Project Review — Scoring Algorithm & Power Scheduler

> Companion to `presentation-guide.md`. Derived from reading the actual call chain:
> `scoring.py`, `cluster_data.py`, `handle_llm_request.py`, both `power_scheduler.py`
> files, `log_reader.py`, `start_test.py`. This is how the code really works, not a
> paraphrase of the report.

---

# Part A — Scoring Algorithm (Cluster Selection)

### Where it lives and when it runs
`handle_llm_request()` runs **once per request**. The scoring code is
`global_api/services/scoring.py`. The data it scores comes from `cluster_data.py`.

### The per-request flow (`handle_llm_request.py`)
1. `config_store.get()` — current run config.
2. `compute_simulated_now(start_time_simulated, start_time_real)` — maps wall-clock now
   onto the simulated timeline.
3. Read recent `RequestLog`s within `latency.latency_window_s`, build
   `avg_latency_by_cluster` (mean of `latency_ms`, the **end-to-end** time, per cluster;
   `0.0` if none).
4. For each cluster → `get_cluster_runtime_data(...)` → a `ClusterRuntimeData`.
5. `choose_cluster(...)` → picks the winner.
6. Recompute blended numbers for the log, forward the question to the winner's cluster
   API, write a `RequestLog`.

### `get_cluster_runtime_data()` — building the inputs (`cluster_data.py`)
For a 1-hour simulated window `[t, t+1h]`:
- `renewable_output_w` = `market_data_store.get_power(...)[0][1]` (PV capacity × hourly
  capacity factor).
- `grid_carbon_intensity` = carbon for that hour.
- `grid_electricity_price` = price **/ 1000** (converts EUR/MWh → EUR/kWh).
- Logs a `MarketSnapshotLog` once per (config, cluster, hour).
- GETs `/get_cluster_working_nodes` from the cluster, counts `WORKING` → `active_nodes`,
  `IDLE` → `idle_nodes`.
- `cluster_load_w = compute_cluster_load(active, idle, energy)` then **+ microgrid base
  load** (for DK, real CROM consumption like a fridge; 0 elsewhere).
- `all_nodes_powered_off = active==0 and idle==0`.

```
compute_cluster_load = active*P_active*scale + idle*P_idle*scale
                     # P_active=6.10W, P_idle=1.19W, scale(power_scale_factor)=50
```

> **Key coupling for the defense:** the grid fraction uses this *measured* `cluster_load_w`.
> More nodes powered on → higher load → lower renewable fraction → **higher** blended
> carbon. So the power scheduler's decisions feed back into the scorer's inputs.

### `score_cluster()` — the math, line by line
```
grid_fraction   = if load<=0 -> 0; else 1 - min(renewable/load, 1.0)   # clamped to [0,1]
blended_carbon  = grid_carbon_intensity * grid_fraction
blended_cost    = round(grid_price * grid_fraction, 4)
norm_carbon     = round(max(1 - blended_carbon/carbon_ref_max, 0), 4)   # carbon_ref_max=670
norm_cost       = round(max(1 - blended_cost /cost_ref_max,   0), 4)   # cost_ref_max=0.30
norm_latency    = round(max(1 - avg_latency /latency_ref_max,0), 4)   # latency_ref_max=12000
score = round(w_gco2*norm_carbon + w_cost*norm_cost + w_latency*norm_latency, 4)
```
Each `normalize_value` is `1 - value/ref_max`, floored at 0, so **higher is better** and a
metric at/above its reference max contributes 0.

### `choose_cluster()` — selection
Loops clusters, **skips any with `all_nodes_powered_off`**, scores the rest, keeps the max
with **strict `>`** so on a tie the **first-scored (config order) wins**. Returns
`(best_cluster, its_runtime_data)`.

Three subtleties worth saying out loud:
1. grid fraction and renewable fraction are both clamped, so surplus renewable is wasted
   (no negative carbon, no storage).
2. latency input is `0` when a cluster has no recent traffic, which normalizes to the
   *best* score.
3. price unit conversion (EUR/MWh → EUR/kWh) happens in `cluster_data`, not in scoring.

---

# Part B — Power Scheduler (the one you didn't write)

Two halves that talk over HTTP:
- **Global half** (`global_api/services/power_scheduler.py`) — decides *how many* nodes
  and *which clusters* get them.
- **Cluster half** (`cluster_api/services/power_scheduler.py`) — flips GPIO / SSHs nodes
  off and picks *which* physical nodes.

### Lifecycle
`start_test()` → if `config.power_scheduler.start`, spawns a **daemon thread** running its
own asyncio loop (`_run_power_scheduler_loop` → `power_scheduler_loop()`). `stop_test()` →
`config_store.stop_power_scheduler()`.

### `power_scheduler_loop()` — the control loop
```
while True:
    config = config_store.get(); if None: break
    await asyncio.sleep(config.power_scheduler.timeout_s)   # WAITS FIRST, then acts
    latest = config_store.get(); if None or not power_scheduler.start: break
    all_clusters = config_store.get_cluster_information()
    turn_nodes_on(latest, all_clusters)      # scale up first
    turn_off_idle_nodes(latest)              # then scale down
```
It **sleeps before the first action**, so initial readiness is handled by
`ensure_nodes_ready()` in `start_test`, not here.

### `turn_nodes_on()` — scaling up

**Step 1 — rank clusters by score.** Calls `_get_scored_clusters()` (same blended scoring
as cluster selection) and sorts descending. *This is the link between the two components:
extra capacity is added to the best-scoring cluster first.*

**Step 2 — read three live signals:**
- `avg_llama_latency_ms` = `get_avg_llama_latency(...)` → mean of
  `RequestLog.cluster_llama_inference_ms` (**inference only**, excludes queue).
- `current_active_nodes` = `get_current_active_nodes(...)` → count of `WORKING` + `IDLE`
  across **all** clusters.
- `current_rps` = `get_current_rps(...)` → count of `LogSent` in the window / window
  seconds (`LogSent` = a request leaving the workload generator).

**Step 3 — guards:** if `current_rps <= 0` → return (no demand). If
`avg_llama_latency_ms <= 0` → return (no data).

**Step 4 — throughput estimate** (`estimate_nodes_to_add` → `estimate_required_nodes`):
```
service_rate_rps = 1000 / avg_llama_latency_ms      # req/s one node can serve
required_nodes   = ceil(current_rps / service_rate_rps)
if active <= 0: return max(1, required_nodes)
else:           nodes_to_add = max(0, required_nodes - active)
```

**Step 5 — latency feedback estimate** (`apply_lantecy_scaling`):
```
if avg > max and active>0:
    scale = avg / max
    scaled_needed = ceil(active * scale)
    return scaled_needed - active
else: return 0
```
> WARNING — discrepancy: in `turn_nodes_on` this is called with `avg_llama_latency_ms`
> (inference-only). The paper describes the latency safety signal as **observed
> end-to-end** latency, and the *turn-off* path uses end-to-end (`get_avg_latency`). So
> turn-on and turn-off use different latency definitions. Decide before the exam whether
> to call this deliberate or own it as an inconsistency.

**Step 6 — combine and place:** `nodes_to_add = max(throughput, latency)`. Then walk the
score-sorted clusters; for each, `amount = min(nodes_to_add, OFF_nodes_in_cluster)`, POST
`/turn_on_nodes?number_of_nodes=amount`, subtract what came back, stop at 0. So it's a
**global capacity calculation with per-cluster, score-ordered placement.**

### `turn_off_idle_nodes()` (global) — scaling down
```
avg = get_avg_latency(...)                 # END-TO-END this time
if avg > config.latency.max_ms: return     # SLO guard: don't shrink while degraded
for each cluster: POST /turn_off_idle_nodes?idle_time=idle_time_for_turn_off_s
```

### Cluster half — execution (`cluster_api/services/power_scheduler.py`)

`change_node_status(n, status)`:
- **"on":** `select_nodes_to_turn_on` (first `n` `OFF` nodes) → `ThreadPoolExecutor` runs
  `turn_on_node` **concurrently** → `wait_for_nodes_to_be_ready`.
- **"off":** `select_nodes_to_turn_off` (first `n` `IDLE` nodes) → `turn_off_node`
  **sequentially**.

`turn_on_node`: **GPIO pulse** — `gpioset gpiochip4 {gpio}=1`, `sleep 0.5`, `=0` (mimics a
power-button press through the optocoupler). Status → `TURNING_ON`.

`wait_for_nodes_to_be_ready` (poll up to 300s): a node is ready only when its
`llama-server` pod is **Running + passes the readiness probe** *and*
`refresh_worker_capacity` reads `total_slots > 0` from the pod's `/props`. Then status →
`IDLE`. On timeout, unready nodes → `OFF`, `max_slots=0`.

`turn_off_node`: status → `TURNING_OFF`, `sleep 10`, **abort if `inflight_requests > 0`**
(back to `IDLE`), else **SSH `sudo -S shutdown now`** (paramiko; username = password = node
name), `sleep 20`, status → `OFF`. Any error → back to `IDLE`. So turn-off is a **graceful
OS shutdown**, not a GPIO cut.

`turn_off_idle_nodes` (cluster side): sorts nodes by name, **`keeper = nodes[0]` is never
turned off** (this enforces ">=1 node per cluster"). For every other node: skip unless
`IDLE`, skip if `inflight > 0`, compute idle age via `get_idle_time` (age of the latest
`IDLE` `NodeStatusLog`, else 0), and if `age > idle_time` → `turn_off_node`.

### The signal map
| Signal | Source | Used for |
|---|---|---|
| `current_rps` | `LogSent` count / window | throughput scale-up |
| `avg_llama_latency_ms` | `RequestLog.cluster_llama_inference_ms` | service rate + (turn-on) latency scaling |
| end-to-end `avg_latency` | `RequestLog.latency_ms` | turn-off SLO guard |
| node idle age | latest `NodeStatusLog` | turn-off eligibility |

**Anti-flapping:** the only hysteresis is the idle threshold (a node must sit `IDLE` for
`idle_time_for_turn_off_s` before it can be killed) plus the SLO guard. There's **no
explicit cooldown** between a turn-on and a subsequent turn-off.

---

# Part C — Project Review

### Strengths
1. **Real hardware, not just simulation.** GPIO power control through optocouplers, SSH
   graceful shutdown, real Jetson Nano inference. The genuine differentiator from the
   related work (which simulates or tests one fixed strategy).
2. **Reproducibility as a first-class design goal.** Simulated-time replay, fixed seed,
   identical workload across weight configs, scoring anchored to the same simulated
   moment. Methodologically strong and unusual at bachelor level. Best 12-grade argument.
3. **Real + reputable data.** Live CROM microgrid data, Copernicus PV, Electricity Maps.
   Direct (not lifecycle) emission factors, justified.
4. **Honest, critical results.** Reporting that balanced did *not* land in the middle and
   explaining *why* (reference-maxima compression) is a hallmark of top grades.
5. **Clean architecture and engineering hygiene.** Three-tier separation, `X-Trace-Id`
   correlation, structured logs to Postgres, ruff + docstrings + tests + k3d CI.
6. **Thoughtful power scheduler.** Two complementary scale-up signals plus real safety
   guards (SLO, in-flight, keeper, pod-readiness gate).

### Weaknesses
1. **Scale and scope.** Two clusters, 8 rpm, single global scheduler instance, one short
   question with 30 tokens. Limits generalizability.
2. **Reported numbers are model outputs, not measurements.** Energy is reconstructed from
   piecewise-constant node states × a hardcoded scale factor of 50, with PV fixed at
   1500 W and fixed reference maxima. "53% reduction" is comparative, not a real-world
   measurement.
3. **The normalization is mis-calibrated, and it wasn't fixed.** The balanced-config
   anomaly is framed as a finding, but it's also a design flaw (latency dominates because
   carbon/cost saturate at the top of the range and latency ref max 12000 ms is below
   observed ~20000 ms).
4. **No battery/storage model.** Surplus renewable is silently wasted.
5. **Power scheduler latency-signal inconsistency** (inference-only on turn-on vs
   end-to-end on turn-off) and **no automated tests** for it.
6. **Limited statistical rigor.** 4 runs, 2 repeats, "they're close" rather than
   variance/confidence intervals.
7. **Concurrency.** A daemon thread mutates shared `WorkerNode` state the request path
   also reads; the cluster-side router uses a lock, but the global side is less clear.

### Grade estimate (Danish 7-point scale)
Realistically **10, with a credible reach to 12** if the defense is sharp; floor around
**7** if the anomaly and the constants can't be explained confidently. The report has the
substance; the 10→12 gap is almost entirely defense quality — demonstrating deep
understanding of the limitations.

### How to push the grade up at the exam
1. **Own every limitation with a fix attached.** Pre-empting beats being caught.
2. **Have the balanced-config explanation cold.** Most likely deep-dive. Be able to draw
   why low-carbon grids + European-scale reference maxima compress carbon/cost into a thin
   band while latency spans the full range.
3. **Best move if you have a spare day:** re-run balanced with *calibrated* reference
   maxima (latency ref ~ observed max; carbon/cost refs ~ actual Nordic range) and show it
   now lands between the extremes. Converts the headline weakness into a demonstrated fix.
4. **Resolve the latency-signal inconsistency** before the exam — justify it or fix the
   one-line call.
5. **Be able to derive every equation and the origin of every constant** (670, 0.30,
   12000, scale 50, 1500 W) on the whiteboard.
6. **Frame threats to validity explicitly** — scale, two countries, reconstructed energy,
   no storage — and what you'd measure next.

### Questions you're most likely to get

**Scoring:**
- Why a linear weighted sum rather than lexicographic ordering or Pareto selection?
- Why *fixed* reference maxima over min-max, and where do 670 / 0.30 / 12000 come from?
- Why did equal weights **not** produce a midpoint? (the big one)
- Renewable > load, or zero load — what happens? (clamped to [0,1], surplus wasted)
- Isn't latency double-counted between the scorer and the power scheduler?
- Does config order bias results, given ties go to the first-scored cluster?
- The grid fraction depends on `cluster_load`, which the power scheduler changes —
  describe that feedback loop. Can it oscillate?

**Power scheduler:**
- Walk through one loop iteration end to end.
- Why `max` of the two scale-up signals, not sum or average?
- Derive the throughput formula — what queueing assumption justifies "linear capacity"?
- Why always keep one node on?
- Race conditions: a request arrives mid-turn-off — what protects you? (`sleep 10` then
  in-flight re-check, abort to IDLE)
- Why GPIO pulse + optocoupler to turn on, but SSH shutdown to turn off?
- What prevents flapping? (idle threshold + SLO guard; no explicit cooldown)
- What if a node never becomes ready? (300s timeout → forced `OFF`)
- Why does turn-on use inference latency but turn-off use end-to-end?

**General / methodology:**
- How valid is "53%" given reconstructed energy and scale factor 50?
- Why only two clusters and 8 rpm? How would it scale? (single global scheduler bottleneck)
- Why no battery model, and how would it change results?
- How reproducible is it really, given each request issues a fresh DB read and HTTP hops?

---

# Part D — Model Answers to the Likely Questions

> Rehearse from these. Each is a few sentences you can compress to a couple of spoken
> lines. Where the honest answer is "that's a limitation," say so and attach the fix.

## Scoring

**Q: Why a linear weighted sum rather than lexicographic ordering or Pareto selection?**
The weighted sum gives a single tunable scalar that maps directly onto operator intent:
the weights sum to one and express a continuous trade-off, and it produces a total order
over clusters so we can always pick one to route to. Lexicographic ordering would make the
secondary metrics irrelevant unless the primary ties exactly, which is brittle, especially
since the energy data is hourly and near-ties are common. Pareto selection returns a *set*
of non-dominated clusters, not a single choice, so we'd still need a scalarization to route
one request, and the weighted sum is the simplest interpretable scalarization. The honest
cost: a linear sum can't reach concave regions of the trade-off front, and equal weights
don't guarantee a balanced outcome, which is exactly what we observed.

**Q: Why fixed reference maxima over min-max, and where do 670 / 0.30 / 12000 come from?**
Min-max normalizes relative only to the clusters currently being compared, which throws
away absolute magnitude and creates misleading ties. Our example: cluster A is ten times
cheaper than B for about ten percent more carbon, clearly better, but min-max ties them
under equal weights. Fixed reference maxima preserve the absolute scale so a genuinely
better cluster stays better. The values: 670 gCO2/kWh is a worst-case European grid
intensity from the Ember electricity review, 0.30 EUR/kWh is a realistic upper bound on
day-ahead price, and 12000 ms was our chosen maximum acceptable latency. I'll note the
latency value turned out too low versus what we observed under load, around 20000 ms, which
is a calibration weakness we discuss.

**Q: Why did equal weights NOT produce a midpoint between the extremes?**
Because the carbon and cost reference maxima are European worst-case values, but both our
grids, Denmark and France, were low-carbon and low-cost, so the blended carbon and cost
values sat in a narrow band at the top of the normalized range. Normalized carbon spanned
only about 0.094 and cost about 0.044, so after the one-third weight, carbon could move the
score by at most about 0.031 and cost about 0.014. Latency, by contrast, varied across
almost the whole zero-to-one range, near one for an idle cluster and toward zero when
overloaded. So under equal weights the latency term dominated the sum and the balanced run
looked like latency-first. The fix is to make the reference maxima operator-configurable so
they match the observed range, and then equal weights give roughly equal influence.

**Q: What happens when renewable output exceeds load, or load is zero?**
The grid fraction is `1 - min(renewable/load, 1.0)`, floored at zero, with a special case
returning zero when load is non-positive. So if renewable exceeds load, the renewable
fraction clamps to one and the grid fraction is zero, meaning blended carbon and cost are
both zero, the cluster is treated as fully green and free. Crucially the surplus is
discarded, there's no negative carbon and no carry-over to a later hour, because we don't
model storage. Zero load also yields grid fraction zero, but that only arises when a cluster
has no active or idle nodes, and those clusters are skipped anyway via
`all_nodes_powered_off`.

**Q: Isn't latency double-counted between the scorer and the power scheduler?**
No, they use latency for two different decisions. The scorer uses recent end-to-end latency
to decide *where* the next request goes, steering load away from a cluster that's slowing
down within the current capacity. The power scheduler uses latency to decide *how many*
nodes should exist, adding capacity when latency rises and refusing to shut nodes down while
latency is above the limit. One is placement, the other is capacity. They do interact,
adding nodes lowers latency which then changes scores, but that's a feedback loop between
two distinct levers, not redundancy.

**Q: Does config order bias results, given ties go to the first-scored cluster?**
`choose_cluster` uses a strict greater-than, so on an exact tie the first cluster in config
order wins. With scores as floats rounded to four decimals, exact ties are uncommon but
possible, mainly very early in a run when latency is zero for every cluster and the energy
inputs happen to match. The bias is therefore small and deterministic, and we chose
deterministic tie-breaking on purpose because it aids reproducible replay. If it mattered,
randomizing or rotating the tie-break would remove it.

**Q: The grid fraction depends on cluster load, which the power scheduler changes. Can that
feedback loop oscillate?**
There is real coupling: more active nodes raise the cluster load, which lowers the renewable
fraction, which raises blended carbon and slightly lowers the carbon score, so scaling a
cluster up makes it look marginally dirtier to the scorer and diverts some later requests
away. That's *negative* feedback on the carbon term, so it's self-limiting and stabilizing
rather than oscillating. The real oscillation risk is in the power scheduler's own on/off
cycle, which we damp with the idle-time threshold and the latency guard. We don't have a
formal stability proof, which is a fair limitation to raise.

## Power scheduler

**Q: Walk me through one loop iteration.**
It sleeps for the configured timeout, then re-reads the config and stops if the test was
ended. It scores and sorts the clusters, then reads three signals: requests per second from
the dispatch logs, average inference latency, and the current active node count. If there's
no demand or no latency data it returns. Otherwise it computes how many nodes are needed
from the throughput model and from the latency-scaling rule, takes the larger, and powers
that many off-nodes on across clusters best-score-first. Then it tries to scale down: it
reads end-to-end average latency, and if that's above the limit it does nothing, otherwise
it asks each cluster to shut down idle non-keeper nodes that have been idle past the
threshold and have no in-flight requests.

**Q: Why the max of the two scale-up signals, not the sum or average?**
Both signals estimate the same quantity, the number of nodes needed, from two different
assumptions, and we want to satisfy both constraints at once. The throughput model sizes for
the steady-state arrival rate; the latency feedback sizes to pull observed latency back under
the limit. Summing them would double-count, because they're two estimates of one total, not
two additive parts, and would over-provision. Averaging could under-provision when one
signal is right and the other underestimates. Taking the max means we provision for whichever
constraint is currently binding, which is the safe choice when you're protecting a latency
target.

**Q: Derive the throughput formula. What queueing assumption justifies linear capacity?**
One node's average inference time is the observed inference latency, so its service rate is
one thousand divided by that latency, in requests per second. To serve an arrival rate
lambda you need the ceiling of lambda over that service rate, so that total capacity, nodes
times service rate, is at least lambda. That's the stability condition of an M/M/c-style
queue, utilization below one, and it assumes the per-node service rate is constant and
independent of how many requests run concurrently. That assumption is precisely why we add a
second, latency-based signal: under concurrency the slots contend and effective service time
rises, so the throughput model alone underestimates, and the latency feedback corrects it.

**Q: Why always keep one node on?**
Two reasons. First, cold start is expensive: powering a Jetson on and waiting for the
llama-server pod to become ready takes up to about five minutes, so we don't want the next
request to pay that. Second, the scorer skips any cluster whose nodes are all off, so if
every cluster went dark there would be nowhere to route. Keeping one node, the keeper, which
is the lowest-named node on each cluster, guarantees baseline availability.

**Q: A request arrives mid-shutdown. What protects you from a race?**
When shutting a node down we first set it to TURNING_OFF, wait ten seconds, then re-check the
in-flight counter, and if any request arrived in that window we abort and return the node to
IDLE before issuing the SSH shutdown. The router only routes to IDLE or WORKING nodes and
adjusts the in-flight counter under a lock, so a node in TURNING_OFF is excluded from new
work. The remaining window is a request selecting a node just before it flips state, and the
delay plus in-flight re-check is the guard. It isn't a hard transaction across the two
services, so it's best-effort, which I'd note as a limitation.

**Q: Why a GPIO pulse to turn on but an SSH shutdown to turn off?**
When a node is fully off there's no software to talk to, so the only way in is the physical
power button, and the GPIO pulse through the optocoupler simulates exactly that button press
with electrical isolation. When a node is running we want a graceful OS shutdown so
Kubernetes drains and the filesystem syncs cleanly, which SSH `sudo shutdown` gives us.
Cutting power over GPIO would be a hard yank and risk corrupting the OS or K3s state. So:
hardware press to wake, software shutdown to sleep.

**Q: What prevents flapping, rapidly toggling a node on and off?**
The idle-time threshold is the main hysteresis: a node has to stay continuously idle for the
configured time before it's even eligible to be powered off, so a node we just turned on
won't be immediately killed. The latency guard also blocks any shutdown while end-to-end
latency is above the limit, and the keeper guarantees we never drop below one node. What we
don't have is an explicit cooldown timer between a scale-up and a scale-down, and since both
run in the same cycle that would be a reasonable improvement.

**Q: What if a node never becomes ready after power-on?**
The readiness wait polls for up to five minutes for the pod to be Running and Ready with a
positive slot count. If a node never gets there, on timeout it's forced to OFF with zero
slots and a warning is logged, so a stuck node neither blocks the cluster nor gets falsely
marked usable, it's simply excluded from routing.

**Q: Why does turn-on use inference latency but turn-off use end-to-end latency?**
I'll be straight that this looks inconsistent. The defensible part: for scale-up throughput
you want the pure per-node service rate, which is inference time, because queue time is the
thing you're adding nodes to remove, and including it would be circular. For the scale-down
guard you want user-visible end-to-end latency, because that's the quality of service you
must protect before removing capacity. The genuinely inconsistent piece is that the
latency-scaling term inside turn-on also uses inference latency, whereas the paper describes
it as end-to-end, and that specific call is the one I'd either justify explicitly or fix.

## General / methodology

**Q: How valid is the 53 percent figure given reconstructed energy and a scale factor of 50?**
It's a relative comparison between two runs that use the identical reconstruction method,
the same scale factor, the same PV capacity and the same reference maxima. Those constants
affect the absolute gram numbers but cancel out of the ratio, so they don't distort the
percentage difference between carbon-first and latency-first. So the relative claim is
robust; what isn't valid is treating the absolute gCO2 numbers as real-world measurements,
and we deliberately frame them as comparative outputs rather than absolute values.

**Q: Why only two clusters and eight requests per minute, and how would it scale?**
It's hardware-limited, we built two physical Pi-plus-Jetson clusters, and eight per minute
keeps a six-hour run at a tractable 2880 requests for the frontend and database. On scaling,
the global scheduler is a single instance that does a database read and a per-cluster runtime
fetch on every request, so per-request overhead grows with cluster count and request rate,
which makes it the bottleneck. The future-work answer is to run the global scheduler on
Kubernetes for horizontal scaling and to cache or batch the runtime data. We don't claim it's
validated at scale.

**Q: Why no battery model, and how would it change the results?**
Storage was out of scope. Without it, any surplus renewable when production exceeds load is
discarded rather than stored, so the system understates the renewable utilization that's
actually achievable, a battery would let a sunny midday cover an evening request, raising
renewable share and cutting carbon further. It would also feed a state-of-charge term into
the grid-fraction calculation. It's the single biggest realism gap, and a clear next step.

**Q: How reproducible is it really, given a fresh DB read and HTTP hops per request?**
The decisions are reproducible because they're anchored to simulated time over the same
historical energy and price data, with a fixed-seed workload, so the same request at the
same simulated moment sees the same energy inputs. What's not bit-for-bit reproducible is
timing: every run does real HTTP and real inference, so measured latency varies, and that
shifts latency-driven tie-breaks and which requests fail under load. Our repeatability test,
Test 1 versus Test 2, showed runs that are close but not identical, which is the honest
summary: energy-driven behavior reproduces, latency-driven behavior carries runtime variance.
