SELECT
  payload_json->>'cluster_name' AS cluster,
  payload_json->>'worker_node' AS node,
  AVG((payload_json->>'worker_call_ms')::int) AS avg_worker_ms,
  MAX((payload_json->>'worker_call_ms')::int) AS max_worker_ms,
  COUNT(*) AS requests
FROM app_logs
WHERE config_id = 'rantzau11'
AND payload_json->>'event' = 'cluster_api.llm.request_succeeded'
GROUP BY cluster, node
ORDER BY avg_worker_ms DESC;