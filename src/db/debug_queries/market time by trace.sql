-- Market/runtime-data time by trace_id.
-- Shows how much time each trace spent before the global scheduler forwarded to cluster_api.
SELECT
  payload_json->>'trace_id' AS trace_id,
  COUNT(*) AS cluster_samples,
  SUM((payload_json->>'pv_fetch_ms')::int) AS total_pv_fetch_ms,
  SUM((payload_json->>'carbon_fetch_ms')::int) AS total_carbon_fetch_ms,
  SUM((payload_json->>'price_fetch_ms')::int) AS total_price_fetch_ms,
  SUM((payload_json->>'load_compute_ms')::int) AS total_load_compute_ms,
  SUM((payload_json->>'latency_lookup_ms')::int) AS total_latency_lookup_ms,
  SUM((payload_json->>'total_runtime_data_ms')::int) AS total_market_runtime_ms,
  MAX(payload_json->>'slowest_step') AS worst_step,
  MAX((payload_json->>'slowest_step_ms')::int) AS worst_step_ms
FROM app_logs
WHERE config_id = 'REPLACE_WITH_CONFIG_ID'
  AND payload_json->>'event' = 'global_api.cluster.runtime_data_timing'
  AND payload_json->>'service' = 'global_api'
GROUP BY payload_json->>'trace_id'
ORDER BY total_market_runtime_ms DESC;
