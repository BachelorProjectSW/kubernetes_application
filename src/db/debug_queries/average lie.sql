-- Latency percentiles for global scheduler
SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY (payload_json->>'global_total_time_ms')::int) AS p50_ms,
  percentile_cont(0.90) WITHIN GROUP (ORDER BY (payload_json->>'global_total_time_ms')::int) AS p90_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY (payload_json->>'global_total_time_ms')::int) AS p95_ms,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY (payload_json->>'global_total_time_ms')::int) AS p99_ms,
  COUNT(*) AS total_requests
FROM app_logs
WHERE config_id = 'rantzau12'
  AND payload_json->>'event' = 'global_api.llm.request_completed'
  AND payload_json->>'service' = 'global_api';