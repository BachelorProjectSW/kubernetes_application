-- Slowest requests across all services
SELECT
  payload_json->>'trace_id' AS trace_id,
  MIN(created_at) AS first_log,
  MAX(created_at) AS last_log,
  EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) * 1000 AS observed_total_ms,
  (SELECT (payload_json->>'global_total_time_ms')::int FROM app_logs 
    WHERE config_id = 'rantzau12' 
    AND payload_json->>'trace_id' = app_logs.payload_json->>'trace_id'
    AND payload_json->>'event' = 'global_api.llm.request_completed' LIMIT 1) AS global_reported_ms
FROM app_logs
WHERE config_id = 'rantzau12'
  AND payload_json::jsonb ? 'trace_id'
GROUP BY payload_json->>'trace_id'
ORDER BY observed_total_ms DESC
LIMIT 20;