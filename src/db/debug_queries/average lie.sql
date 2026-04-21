SELECT
  percentile_cont(0.50) WITHIN GROUP (ORDER BY (payload_json->>'total_ms')::int) AS p50,
  percentile_cont(0.90) WITHIN GROUP (ORDER BY (payload_json->>'total_ms')::int) AS p90,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY (payload_json->>'total_ms')::int) AS p99
FROM app_logs
WHERE config_id = 'rantzau11'
AND payload_json->>'event' = 'global_api.llm.request_completed';