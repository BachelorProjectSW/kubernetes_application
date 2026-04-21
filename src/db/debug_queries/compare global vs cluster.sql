-- Compare global scheduler time vs cluster worker time
-- Shows queueing delay = global_total - (cluster_total + network_call)
SELECT
  g.payload_json->>'trace_id' AS trace_id,
  (g.payload_json->>'global_total_time_ms')::int AS global_total_ms,
  (g.payload_json->>'global_market_data_fetch_ms')::int AS market_fetch_ms,
  (g.payload_json->>'global_cluster_scoring_ms')::int AS scoring_ms,
  (g.payload_json->>'global_cluster_api_call_ms')::int AS api_call_ms,
  (c.payload_json->>'cluster_total_time_ms')::int AS cluster_total_ms,
  (c.payload_json->>'cluster_llama_inference_ms')::int AS llama_inference_ms,
  (g.payload_json->>'global_total_time_ms')::int - (c.payload_json->>'cluster_total_time_ms')::int AS queue_wait_ms
FROM app_logs g
JOIN app_logs c
  ON g.payload_json->>'trace_id' = c.payload_json->>'trace_id'
  AND g.config_id = c.config_id
WHERE g.config_id = 'rantzau12'
  AND g.payload_json->>'event' = 'global_api.llm.request_completed'
  AND g.payload_json->>'service' = 'global_api'
  AND c.payload_json->>'event' = 'cluster_api.llm.request_succeeded'
  AND c.payload_json->>'service' = 'cluster_api'
ORDER BY (g.payload_json->>'global_total_time_ms')::int DESC
LIMIT 20;