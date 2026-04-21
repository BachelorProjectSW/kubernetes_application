-- Global API request timing breakdown (each step separately)
SELECT
  payload_json->>'trace_id' AS trace_id,
  (payload_json->>'global_market_data_fetch_ms')::int AS market_fetch_ms,
  (payload_json->>'global_cluster_scoring_ms')::int AS scoring_ms,
  (payload_json->>'global_cluster_api_call_ms')::int AS api_call_ms,
  (payload_json->>'global_total_time_ms')::int AS total_global_ms,
  (payload_json->>'global_market_data_fetch_ms')::int + (payload_json->>'global_cluster_scoring_ms')::int AS pre_call_total_ms,
  ((payload_json->>'global_total_time_ms')::int - (payload_json->>'global_cluster_api_call_ms')::int) AS queue_time_ms
FROM app_logs
WHERE config_id = 'rantzau12'
  AND payload_json->>'event' = 'global_api.llm.request_completed'
  AND payload_json->>'service' = 'global_api'
ORDER BY (payload_json->>'global_total_time_ms')::int DESC
LIMIT 50;