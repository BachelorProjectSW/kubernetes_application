# `src/custom_logging/models/log_models.py` — the five log schemas

Pure Pydantic schemas. Every structured log that round-trips through `app_logs` is one of these;
the `log_type` column stores the class name. They're the "shape" of all telemetry.

### `RequestLog` (6–26) — the per-request telemetry row (the big one)
The richest model; one row per completed request, written by `log_request`. Fields worth knowing:
- `trace_id` — the correlation id across services.
- `latency_ms` — **end-to-end** latency (set from `global_total_time_ms`). *This* is what
  `get_avg_latency` averages.
- `cluster_load_w`, `renewable_fraction`, `blended_carbon_gco2_per_kwh`, `blended_cost_eur_per_kwh`
  — the energy snapshot at decision time.
- `question`, `answer`, `response_status_code`, `all_content` — the Q&A payload.
- **`global_choose_cluster`** — how long scoring took.
- **`global_total_time_ms`** — end-to-end (mirrors `latency_ms`).
- **`cluster_queue_time_ms`** / **`cluster_llama_inference_ms`** — the **queue vs inference**
  split. `cluster_llama_inference_ms` is what `get_avg_llama_latency` averages.
- This single model carries the **three latencies** (end-to-end / queue / inference) that the
  whole latency discussion rests on, and everything the dashboard charts.

### `NodeStatusLog` (29–35)
`timestamp, cluster, node, status` — a node's state at a moment. Powers the dashboard's node
timeline and `test_results`' energy reconstruction (it integrates power over these transitions).

### `MarketSnapshotLog` (38–49)
`simulated_hour, cluster, carbon_gco2_per_kwh, cost_eur_per_kwh` — hourly market rates, written
once per (config, cluster, hour). The docstring says it exists to give `test_results` accurate
hourly rates for the authoritative carbon/cost totals.

### `TerminalDebugLog` (52–58)
`config_id, message, payload, created_at` — schema for terminal/debug log rows. (Note: the actual
terminal save path in `postgres.save_terminal_debug` builds an `AppLogRecord` directly, so this
model is more a declared shape than a hot-path object.)

### `LogSent` (61–67)
`timestamp, cluster, trace_id, payload` — the **dispatch** marker Strato writes per request.
Counting these over a window gives **λ (RPS)** for the power scheduler (`get_sent_logs`).

## In short
> One rich model (`RequestLog`, carrying the three latencies + energy) plus four light ones
> (`NodeStatusLog`, `MarketSnapshotLog`, `TerminalDebugLog`, `LogSent`). All persist to the single
> `app_logs` table, keyed by `config_id` + `log_type`, and are read back by `log_reader.py` /
> `test_results.py`.
