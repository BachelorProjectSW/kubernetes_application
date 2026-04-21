-- Follow a specific trace_id through all services
SELECT
  created_at,
  payload_json->>'service' AS service,
  payload_json->>'event' AS event,
  payload_json->>'trace_id' AS trace_id,
  CASE 
    WHEN payload_json->>'service' = 'global_api' AND payload_json->>'event' = 'global_api.llm.request_completed' 
      THEN (payload_json->>'global_total_time_ms')::int
    WHEN payload_json->>'service' = 'cluster_api' AND payload_json->>'event' = 'cluster_api.llm.request_succeeded'
      THEN (payload_json->>'cluster_total_time_ms')::int
    ELSE NULL
  END AS timing_ms,
  payload_json
FROM app_logs
WHERE config_id = 'rantzau12'
  AND payload_json->>'trace_id' = 'REPLACE_WITH_TRACE_ID'
ORDER BY created_at;