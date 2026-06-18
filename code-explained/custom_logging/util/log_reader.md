# `src/custom_logging/util/log_reader.py` — reading logs back (where issue B is grounded)

Thin read helpers over `postgres.read_model_logs`. Most are trivial, but **two functions define
exactly which stored field counts as "latency,"** and that distinction *is* the code-vs-report
latency inconsistency (issue #2) you've been tracking. So this short file is where that issue
physically lives.

---

## The two latency readers (the important pair)

### `get_avg_latency(config_id, window, cluster=None)` (6–35) → END-TO-END
```python
33      latencies.append(request_log.latency_ms)
35  return round(sum(latencies) / len(latencies), 2) if latencies else 0.0
```
- Averages **`RequestLog.latency_ms`** over the window, successful requests only.
- **`latency_ms` is the END-TO-END latency** — it's set in `handle_llm_request` from
  `global_total_time_ms` (the whole Strato→…→answer time). The docstring even calls it "average
  response time."
- **Consumed by:** the power scheduler's **turn-off SLO guard** (`turn_off_idle_nodes`: skip the
  pass if `get_avg_latency > max_ms`). So scaling *down* is gated on end-to-end latency.

### `get_avg_llama_latency(config_id, window, cluster=None)` (38–67) → INFERENCE
```python
63      latencies.append(request_log.cluster_llama_inference_ms)
67  return round(sum(latencies) / len(latencies), 2) if latencies else 0.0
```
- Identical shape, but averages **`RequestLog.cluster_llama_inference_ms`** — the **inference
  time only** (the `/completion` call measured in `llm.py:244`), excluding queue/overhead. The
  docstring: "time Llama model spent running... excluding queue and overhead time."
- **Consumed by:** the power scheduler's **throughput model** (`μ = 1000/inference`) **and** the
  **latency-feedback `S` term** (`apply_lantecy_scaling`).

### ★ This is where issue #2 lives
- The throughput model using inference latency is **correct** and matches the report's
  service-time definition.
- But the **latency-feedback `S = L_obs/L_max`** is *also* fed `get_avg_llama_latency`
  (inference), while the report's eq 10 defines **`L_obs` as end-to-end**. Both inference and
  end-to-end are available here (these two functions); the scheduler simply calls the inference
  one for `S`. So the fix would be a one-line change: feed `apply_lantecy_scaling` the result of
  `get_avg_latency` (end-to-end) instead of `get_avg_llama_latency`. Good concrete answer if
  pushed: *"the two measures are both computed in `log_reader.py`; we wired the inference one into
  the latency term, the report assumes the end-to-end one."*

---

## The rest (straightforward readers)
- **`read_all_request_logs(config_id)` (70–83)** — all `RequestLog`s for a run (success+fail);
  empty list on bad id / DB error. Used by `test_results`.
- **`get_config_by_id(config_id)` (86–95)** — load the `Config`; `None` on miss/error.
- **`get_sent_logs(config_id, window)` (98–112)** — `LogSent` rows in the window; **this is what
  `get_current_rps` counts to compute λ** for the power scheduler.
- **`read_all_sent_logs` (115–128)** — all `LogSent`s (for dispatch-pattern analysis).
- **`get_worker_nodes_logs(config_id, cluster, node)` (131–144)** — latest `NodeStatusLog` for one
  node; backs the cluster-side `get_idle_time` (idle-age calculation for turn-off).
- **`read_all_node_status_logs` (147–153)** — full node-status history (powers the dashboard
  timeline and the `test_results` energy reconstruction).
- **`read_all_market_snapshot_logs` (156–162)** — hourly carbon/price snapshots (used by
  `test_results` for the authoritative carbon/cost totals).

All wrap `read_model_logs` and (except the `read_all_*` analysis ones) swallow errors into empty
results, telemetry reads must never break a live decision.

## Defense-worthy points
- **`get_avg_latency` = end-to-end (`latency_ms`); `get_avg_llama_latency` = inference
  (`cluster_llama_inference_ms`).** Memorize which is which.
- **Issue #2 is a one-call wiring choice here:** the `S` term is fed the inference reader; the
  report assumes the end-to-end one. Both readers exist side by side.
- **`get_sent_logs` is the source of λ (RPS)** for the throughput model.
