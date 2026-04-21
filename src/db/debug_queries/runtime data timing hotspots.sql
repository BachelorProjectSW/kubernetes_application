-- Show runtime-data timing breakdown per cluster and request step.
SELECT
  created_at,
  payload_json->>'cluster_name' AS cluster_name,
  (payload_json->>'pv_fetch_ms')::int AS pv_fetch_ms,
  (payload_json->>'carbon_fetch_ms')::int AS carbon_fetch_ms,
  (payload_json->>'price_fetch_ms')::int AS price_fetch_ms,
  (payload_json->>'load_compute_ms')::int AS load_compute_ms,
  (payload_json->>'latency_lookup_ms')::int AS latency_lookup_ms,
  payload_json->>'slowest_step' AS slowest_step,
  (payload_json->>'slowest_step_ms')::int AS slowest_step_ms,
  (payload_json->>'total_runtime_data_ms')::int AS total_runtime_data_ms
FROM app_logs
WHERE config_id = '44dc3b8a-38db-400f-a5cb-8f186d8dc9c9'
  AND payload_json->>'event' = 'global_api.cluster.runtime_data_timing'
  AND payload_json->>'service' = 'global_api'
ORDER BY slowest_step_ms DESC
LIMIT 100;

-- Aggregate by cluster to identify persistent bottlenecks.
SELECT
  payload_json->>'cluster_name' AS cluster_name,
  COUNT(*) AS samples,
  AVG((payload_json->>'total_runtime_data_ms')::int) AS avg_total_runtime_data_ms,
  AVG((payload_json->>'pv_fetch_ms')::int) AS avg_pv_fetch_ms,
  AVG((payload_json->>'carbon_fetch_ms')::int) AS avg_carbon_fetch_ms,
  AVG((payload_json->>'price_fetch_ms')::int) AS avg_price_fetch_ms,
  AVG((payload_json->>'load_compute_ms')::int) AS avg_load_compute_ms,
  AVG((payload_json->>'latency_lookup_ms')::int) AS avg_latency_lookup_ms,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (payload_json->>'total_runtime_data_ms')::int) AS p95_total_runtime_data_ms
FROM app_logs
WHERE config_id = '44dc3b8a-38db-400f-a5cb-8f186d8dc9c9'
  AND payload_json->>'event' = 'global_api.cluster.runtime_data_timing'
  AND payload_json->>'service' = 'global_api'
GROUP BY cluster_name
ORDER BY avg_total_runtime_data_ms DESC;
