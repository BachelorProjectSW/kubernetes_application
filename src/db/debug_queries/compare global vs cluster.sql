SELECT
  g.payload_json->>'trace_id' AS trace_id,
  g.payload_json->>'total_ms' AS global_ms,
  c.payload_json->>'worker_call_ms' AS worker_ms
FROM app_logs g
JOIN app_logs c
  ON g.payload_json->>'trace_id' = c.payload_json->>'trace_id'
WHERE g.payload_json->>'event' = 'global_api.llm.request_completed'
AND c.payload_json->>'event' = 'cluster_api.llm.request_succeeded';