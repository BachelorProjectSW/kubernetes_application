# `src/global_api/services/handle_llm_request.py` — per-request scheduling

This is the function that runs **once per question** and decides where it goes. It's the
orchestration layer of the global scheduler and the **top of your cluster-selection
component**. The actual scoring math lives in `scoring.py` (next jump); this file's job is to
*gather the inputs*, *call the scorer*, *forward to the chosen cluster*, and *log the
result*.

Shape of the function: one big `try` (37–185) doing the happy path, an inner `try` (110–139)
around the cluster call, and an outer `except` (186–256) that logs whatever failed with
whatever data exists. Most of the file's length is that defensive logging; the *logic* is
lines 37–185.

The five steps of the happy path:
1. read config + compute simulated time (38–45)
2. pull recent latencies, average per cluster (47–65)
3. gather runtime data for every cluster (67–76)
4. **score and pick a cluster** (78–85) ← your component
5. forward the question to that cluster, log the result (104–185)

---

## Imports (1–18)
```python
3   import requests
7   from ...custom_logging.logger import log_request
8   from ...db.postgres import read_model_logs
9   from ...custom_logging.models.log_models import RequestLog
12  from ..util.all_configuration import config_store
13  from ..util.time_utils import compute_simulated_now
14  from .cluster_data import get_cluster_runtime_data
15  from .scoring import choose_cluster, compute_carbon_blend, compute_cost_blend, compute_grid_fraction
```
- **`requests`** — blocking HTTP client; used to forward the question to the cluster API.
  (This handler is a normal sync function, the global API serves each request on its own
  thread, so blocking here is fine.)
- **`read_model_logs`** (8) — the DB reader we documented; pulls recent `RequestLog`s for the
  latency window. **`RequestLog`** (9) is the model it returns.
- **`config_store`** (12) — the in-memory holder of the active `Config` (set at
  `/start_test`). **Jump candidate:** `util/all_configuration.py`.
- **`compute_simulated_now`** (13) — maps wall-clock to simulated time. **Jump candidate:**
  `util/time_utils.py`.
- **`get_cluster_runtime_data`** (14) — gathers per-cluster PV/carbon/price/load. **Jump
  candidate:** `cluster_data.py`.
- **`choose_cluster` + the three blend helpers** (15) — **your scoring component.** Main
  next jump: `scoring.py`.

---

## Step 1: config + simulated time (37–45)
```python
38      total_start = time.monotonic()
39      config = config_store.get()
42      simulated_time = compute_simulated_now(
43          config.start.start_time_simulated,
44          config.start.start_time_real,
45      )
```
- **Line 38** — start a monotonic timer for the **whole** request (used later as
  `global_total_time_ms`, the end-to-end latency this service records).
- **Line 39** — fetch the active config from the in-memory store. This is the config Strato
  sent to `/start_test`; the global API kept it in memory so every request can read it
  without a DB hit.
- **Lines 42–45 — the simulated-time core.** The test replays a *simulated* moment (e.g. a
  sunny noon in July) even though it runs now. `compute_simulated_now` takes the configured
  simulated start and the real start, and returns "where in simulated time are we right now,"
  by adding the real elapsed time to the simulated start. Every energy lookup below uses this
  `simulated_time`, so PV output, carbon, and price are all read for the simulated moment.
  This is what makes runs reproducible and lets you test "what if it were noon in summer."

---

## Step 2: recent latencies, averaged per cluster (47–65)
```python
49      now = datetime.now(timezone.utc)
50      start = now - timedelta(seconds=config.latency.latency_window_s)
52          recent_requests = read_model_logs(RequestLog, config.id, since=start)
57      avg_latency_by_cluster: dict[str, float] = {}
58      for cluster in config.clusters:
59          latencies = [r.latency_ms for r in recent_requests if r.cluster == cluster.name]
60          if latencies:
61              avg = round(sum(latencies) / len(latencies), 2)
62          else:
63              avg = 0.0
65          avg_latency_by_cluster[cluster.name] = avg
```
- **Lines 49–50** — define a sliding window: the last `latency_window_s` seconds (from
  `LatencyConfig`). Only recent latency counts toward scoring, old data shouldn't bias a
  live decision.
- **Line 52** — one DB read for **all** clusters' recent `RequestLog`s for this run
  (`config.id`). The comment on 47–48 calls out the optimization: read once, reuse for every
  cluster, rather than one query per cluster. Wrapped in try/except → on DB failure, fall
  back to an empty list (53–54), so scoring still proceeds (latency just looks like 0).
- **Lines 57–65** — collapse those logs into **one average latency per cluster**: filter the
  window's logs to this cluster, average their `latency_ms`, or `0.0` if none. The result
  `avg_latency_by_cluster` feeds two things downstream: the **latency metric in scoring** and
  (separately, in the background loop) the **power scheduler's latency signal**. This is the
  observed-latency input both of your components consume.
- Note: `latency_ms` here is the **end-to-end** latency the global API recorded per request
  (`global_total_time_ms`, set at line 169). Relevant to the code-vs-report latency nuance
  you've flagged, the scoring/latency-window path uses end-to-end latency.

---

## Step 3: gather runtime data for every cluster (67–76)
```python
68      all_cluster_energy_data = [
69          get_cluster_runtime_data(
70              cluster, simulated_time, config.energy,
73              avg_latency_ms=avg_latency_by_cluster.get(cluster.name),
74          )
75          for cluster in config.clusters
76      ]
```
- For **each cluster**, build its current runtime snapshot: PV/renewable output, grid carbon
  intensity, grid price, current load, and the avg latency we just computed. All looked up at
  `simulated_time`. The result is a list aligned with `config.clusters`, exactly the inputs
  the scorer needs. **Jump candidate:** `cluster_data.py` (it's the data-gathering hub that
  in turn calls `pv_power.py`, `price_and_carbon_intensity.py`, etc.).

---

## Step 4: score and pick (78–85) ← your cluster-selection component
```python
79      cluster, cluster_energy_data = choose_cluster(
80          config.clusters,
81          all_cluster_energy_data,
82          config.weights,
83          config.energy,
84      )
85      choose_cluster_end = int((time.monotonic() - total_start) * 1000)
```
- **Lines 79–84 — the decision.** `choose_cluster` takes the clusters, their runtime data,
  the operator `weights` (carbon/cost/latency), and energy normalization references, and
  returns the **winning cluster and its data**. This is the `score = w_c·carbon + w_e·cost +
  w_l·latency` computation you present, the highest score wins. Everything before this was
  assembling its inputs; everything after is acting on its output. **Main next jump:**
  `scoring.py`.
- **Line 85** — record how long selection took (`global_choose_cluster` in the log), a
  per-request "how expensive is scheduling" metric.

---

## Step 4b: blended numbers for the log (87–102)
```python
88      grid_fraction = compute_grid_fraction(cluster_energy_data.renewable_output_w, cluster_energy_data.cluster_load_w)
92      renewable_fraction = round(max(0.0, 1.0 - grid_fraction), 4)
93      blended_carbon = compute_carbon_blend(...renewable_output_w, ...cluster_load_w, ...grid_carbon_intensity)
98      blended_cost  = compute_cost_blend(...renewable_output_w, ...cluster_load_w, ...grid_electricity_price)
```
- Recompute the chosen cluster's **blended** carbon/cost and its renewable fraction, for the
  telemetry row. These reuse the **same scoring helpers** so the logged numbers match exactly
  what scoring used. `grid_fraction = 1 − renewable/load` (your blending formula);
  `renewable_fraction = 1 − grid_fraction`. We'll cover the actual formulas in `scoring.py`.
- Slight redundancy: scoring already computed these internally; here they're computed again
  for logging. Fine, but worth knowing they're recomputed, not reused.

---

## Step 5: forward to the chosen cluster (104–139)
```python
105     url = f"http://{cluster.ip}:{cluster.port}/handle_llm_request"
107     headers = {"X-Trace-Id": trace_id}
111     response = requests.post(url, json=question.model_dump(), headers=headers, timeout=1000)
117     response.raise_for_status()
118     data = response.json()
119     except Exception as e:
121         global_total_time_ms = int((time.monotonic() - total_start) * 1000)
122         log_request(... success=False ... response_status_code=500 ...)
139         raise
```
- **Line 105 — the next cross-service hop.** The global API forwards the question to the
  **chosen cluster's** `/handle_llm_request`. Note the trace id is **propagated again** (107):
  Strato → global → cluster, same `X-Trace-Id` all the way to the llama pod.
- **Line 111** — blocking POST, `timeout=1000` (same generous LLM timeout as Strato).
- **Lines 110–139** — if the cluster call fails, record a **failed `RequestLog`** with the
  energy data we already have (so the failure is visible in results) and `raise`, which is
  caught by the outer `except` and turned into a 500 back to Strato. This is the global side's
  per-request failure log (distinct from Strato's, which only logs if the request never
  reached *this* host, the no-double-counting split).

---

## Step 5b: parse, extract answer, log success (141–185)
```python
142     result = LLMResponse(llm_content=data["llm_content"], worker_node=data["worker_node"], ...
149         cluster_queue_time_ms=data.get("cluster_queue_time_ms"),
150         cluster_llama_inference_ms=data.get("cluster_llama_inference_ms"), ...)
159     if isinstance(llm_content, dict):
160         answer = llm_content.get("content") or None
162     global_total_time_ms = int((time.monotonic() - total_start) * 1000)
165     log_request(... success=True ... latency_ms=global_total_time_ms ...
181         cluster_queue_time_ms=result.cluster_queue_time_ms,
182         cluster_llama_inference_ms=result.cluster_llama_inference_ms)
185     return result
```
- **Lines 142–152** — parse the cluster's JSON into an `LLMResponse` model. Note the
  **timing breakdown** the cluster returns: `cluster_queue_time_ms` (time the request waited
  in the node's queue) and `cluster_llama_inference_ms` (actual model inference time). These
  use `.get()` (nullable) because not every path returns them. **This split is exactly the
  latency decomposition behind your power-scheduler discussion:** end-to-end vs queue vs
  inference. The global API records all three.
- **Lines 153–160** — pull the worker node and the text answer out of the payload.
- **Line 162** — final end-to-end time for this request.
- **Lines 165–183** — write the **successful `RequestLog`**: the full telemetry row (cluster,
  node, success, end-to-end latency, load, renewable fraction, blended carbon/cost, the Q&A,
  and the three timing fields). This is the row the results dashboard and the scoring latency
  window later read. `global_total_time_ms` is the **end-to-end** latency; the inference-only
  number is stored separately as `cluster_llama_inference_ms`, both are kept, which is what
  lets the report (and you) compare end-to-end vs inference latency.
- **Line 185** — return the `LLMResponse` to the route, which returns it to Strato.

---

## The outer `except` (186–256) — defensive last-resort logging
- One big handler that fires if **anything** above threw outside the inner cluster-call
  try. Its bulk is `"x" if "x" in locals() else default` guards: because a failure could
  happen at *any* step, it can't assume `cluster`, `result`, etc. exist, so it checks
  `locals()` for each before using it. It logs the most complete failed `RequestLog` it can
  assemble, then raises a **500** to the route.
- It's verbose and a little ugly, but the intent is good: **never lose a request to an
  unlogged crash.** Worth a one-line defense answer ("defensive logging so every request,
  even a mid-pipeline failure, leaves a telemetry row"). The `locals()` introspection is the
  code-smell to acknowledge if pushed, a cleaner design would track state in explicit
  variables initialized up front.

---

## What this request touched, and the jump list

```
handle_llm_request
  ├ config_store.get()                         → util/all_configuration.py
  ├ compute_simulated_now(...)                 → util/time_utils.py
  ├ read_model_logs(RequestLog, ...)           → db/postgres.py  (done)
  ├ get_cluster_runtime_data(...) per cluster  → cluster_data.py  (→ pv_power, price_and_carbon, ...)
  ├ choose_cluster(...)                        → scoring.py   ★ your component
  ├ compute_grid_fraction / carbon / cost      → scoring.py
  ├ requests.post(.../handle_llm_request)      → cluster_api  (cross-service, next tier)
  └ log_request(...)                           → custom_logging/logger.py  (done)
```

**Recommended next jump:** `src/global_api/services/scoring.py` — `choose_cluster` and the
blend/normalize helpers. That's the literal core of your Scoring Algorithm slides, the
`score = w_c·carbon + w_e·cost + w_l·latency`, the grid-fraction blending, and the fixed-max
normalization. (We can take `cluster_data.py` and the two small util files either before or
after; scoring is the one you most need airtight.)
