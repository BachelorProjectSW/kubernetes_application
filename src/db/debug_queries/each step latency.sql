SELECT
  payload_json->>'trace_id' AS trace_id,
  (payload_json->>'runtime_fetch_ms')::int AS runtime_fetch_ms,
  (payload_json->>'cluster_select_ms')::int AS cluster_select_ms,
  (payload_json->>'cluster_forward_ms')::int AS cluster_forward_ms,
  (payload_json->>'total_ms')::int AS total_ms
FROM app_logs
WHERE config_id = 'rantzau11'
AND payload_json->>'event' = 'global_api.llm.request_completed'
ORDER BY total_ms DESC;