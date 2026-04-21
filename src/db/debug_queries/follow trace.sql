SELECT
  created_at,
  log_type,
  terminal_debug,
  payload_json->>'event' AS event,
  payload_json->>'trace_id' AS trace_id,
  payload_json
FROM app_logs
WHERE config_id = 'rantzau11'
AND payload_json->>'trace_id' = '91c3f117-dcda-47e6-aa9a-e07d32fcc16e'
ORDER BY created_at;