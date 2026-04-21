SELECT
  payload_json->>'trace_id' AS trace_id,
  MIN(created_at) AS start_time,
  MAX(created_at) AS end_time,
  EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) * 1000 AS total_ms
FROM app_logs
WHERE config_id = 'rantzau11'
AND payload_json::jsonb ? 'trace_id'
GROUP BY payload_json->>'trace_id'
ORDER BY total_ms DESC
LIMIT 20;