# `src/models/basemodels.py` — the shared data model (and the `EnergyConfig` constants)

Every service imports these Pydantic models. `Config` is the top-level object the frontend
sends and the DB stores; the rest are its sub-objects plus the runtime/response models. Mostly
this file is plain schema, but **`EnergyConfig` holds the magic constants** (power draw,
scale factor, PV capacity, and the scoring reference maxima), and one of them does **not** match
your slides. Read the `EnergyConfig` section carefully.

---

## The config tree (`Config` and sub-objects)

`Config` (184–198) is the whole test configuration:
```
Config
 ├ id, name
 ├ start: StartConfig          duration_time_s, start_time_simulated (str), start_time_real (set by global)
 ├ weights: WeightsConfig      gco2, cost, latency  (must sum to 1 — enforced in validate_config)
 ├ power_scheduler: PowerSchedulerConfig   start (bool), timeout_s, idle_time_for_turn_off_s
 ├ latency: LatencyConfig       latency_window_s, max_ms (the SLO)
 ├ workload: WorkloadConfig     request_per_minute, pattern("steady"|"peaks"), seed, peakiness
 ├ question: QuestionConfig     question, max_output_tokens
 ├ clusters: list[ClusterConfig]
 ├ global_scheduler / strato: ip, port
 └ energy: EnergyConfig = EnergyConfig()   ← defaulted; the frontend does NOT send this
```
- All are thin Pydantic `BaseModel`s, declaring fields + types. The typing is what lets FastAPI
  validate the request body automatically.
- **`pattern: Literal["steady", "peaks"]`** (44) — the only enum-like constraint; Pydantic
  rejects any other pattern at parse time.
- **`start_time_simulated` is a `str`** (12), parsed later by `compute_simulated_now` /
  `validate_config`. The comment claims it supports several formats, but the parsers use the
  single `dd/mm/yyyy HH:MM:SS` format, so that comment overstates it.
- **`energy: EnergyConfig = EnergyConfig()`** (198) — **defaulted.** Since `submitData.jsx`
  never includes an `energy` block, **every frontend-started run uses these defaults.** That
  makes the constants below the *actual* values used in your experiments.

---

## `WorkerNode` (57–114) — the slot model (already used everywhere)
```python
63  inflight_requests: int = 0
64  max_slots: int = 0
65  gpio: int
66  forwarded_port: int | None = None
68  active_requests  = min(inflight, max_slots)
85  queued_requests  = max(0, inflight − max_slots)
101 free_slots       = max(0, max_slots − active_requests)
```
- The three **computed properties** are the cluster-side scheduling vocabulary (documented in
  `cluster_api/services/llm.md`). `inflight_requests` is the only raw counter; the rest derive
  from it + `max_slots`. CLAUDE.md says reuse these rather than recomputing min/max inline.

---

## `EnergyConfig` (164–181) — the constants that drive energy & scoring

```python
168  node_power_off_w: float = 0
169  node_power_idle_w: float = 1.19
170  node_power_active_w: float = 6.10
173  power_scale_factor: int = 50
176  pv_capacity_w: float = 1500
179  carbon_ref_max: float = 670     # gCO2/kWh
180  cost_ref_max: float = 0.30      # EUR/kWh
181  latency_ref_max: float = 25000  # ms   ← NOT 12000
```

Know these numbers; an energy examiner will ask, and the code round may land here.

- **Per-node power:** OFF draws **0 W**, IDLE **1.19 W**, ACTIVE **6.10 W**. These are the
  measured Jetson-scale figures.
- **`power_scale_factor = 50`** — every node's watts are multiplied by **50** to model a
  realistic data-center-scale cluster. So an active node effectively contributes
  `6.10 × 50 = 305 W` to `cluster_load_w`. (The field's comment, *"How many nanos each nano is
  scaled up to"*, is nonsense, ignore it; it's a leftover typo, the value is a watt multiplier.)
- **`pv_capacity_w = 1500`** — installed PV capacity per cluster; multiplied by the hourly
  capacity factor to get renewable watts.
- **The three reference maxima** for `normalize_value` (`v_norm = max(0, 1 − value/ref_max)`):
  - `carbon_ref_max = 670` gCO₂/kWh ✅ matches your slide.
  - `cost_ref_max = 0.30` EUR/kWh ✅ matches your slide.
  - **`latency_ref_max = 25000` ms ❌ your Normalization slide says 12000 ms.**

### ⚠️ The `latency_ref_max` discrepancy — RESOLVED (and it's a good story)
The code default is **25000 ms**, but the report and your Normalization slide say **12000 ms**.
Git history resolves it definitively:
- The value was **12000** throughout the experiments and the report (paper dated **May 27,
  2026**).
- Commit **c2ca99d "Increase latency reference maximum to 25000 ms"** changed it to 25000 on
  **May 30, 2026**, **three days *after* the report was submitted.**

So **the experiments used 12000 (the report is correct); the code was changed to 25000
afterward.** This is consistent with the report's central discussion, which argues 12000 was
*too low* (latencies of ~20000 ms exceeded it, so latency normalized to ~0 and the balanced
strategy resembled latency-first). The post-report bump to 25000 is plainly a **fix for exactly
that flaw**, which the paper itself flagged as future work (making reference maxima
configurable).

**Exam handling:**
- Keep **12000 on the Normalization slide** — it matches the experiments and the report.
- If the code round opens this file and sees 25000, say: *"All experiments and the report used
  12000. After submitting, we acted on our own discussion, we'd shown 12000 was too low and
  compressed the latency normalization, so we raised it to 25000 to address that. The git
  history shows the change post-dates the report."* That reframes "code ≠ paper" as "we found
  and fixed a flaw in our own analysis."
- Note: with 25000, a 20000 ms latency normalizes to 0.2 (not 0), so the current code would
  *not* reproduce the report's "latency clamps to 0" behaviour, which is the whole point of the
  fix. Be clear that reproducing the *reported* results requires 12000.

---

## Other models
- **`ClusterConfig` (117–127)** — per-cluster: name/ip/port, `gpio_list`, `simulated_country_code`,
  `k3d` flag, and the llama port fields (`llama_service_port` for k3d forwards, `llama_hostport`
  default 8080 for prod). The k3d/llama fields are the test-vs-prod seam.
- **`ClusterRuntimeData` (130–138)** — the per-cluster snapshot scoring consumes (renewable,
  load, carbon, price, avg latency, all-off flag).
- **`ClusterInformation` (141–147)** — what the global API pushes to a cluster at `/set_config`
  (config id + cluster config + question + worker list).
- **`LLMResponse` (201–212)** — the cluster's reply: llama content, the chosen `WorkerNode`, the
  slot snapshot at selection, and the **three timing fields** (`cluster_queue_time_ms`,
  `cluster_llama_inference_ms`, plus end-to-end recorded upstream). The latency decomposition
  surfaces here.

## Defense-worthy points
- **`EnergyConfig` is defaulted and the frontend never overrides it**, so its constants are your
  real experimental parameters. Know `power_scale_factor=50`, idle/active 1.19/6.10 W, PV 1500 W.
- **`latency_ref_max=25000` vs slide's 12000** — reconcile before the exam (see above).
- **`power_scale_factor` comment is wrong** ("nanos"), a doc bug to acknowledge if spotted.
