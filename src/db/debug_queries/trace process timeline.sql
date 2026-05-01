-- Process timeline for all trace_id values.
-- Shows when each step happened and which cluster/node was chosen.
WITH params AS (
  SELECT '2e4168b2-bb0e-4bf3-b8f0-c70c70d6898c'::text AS config_id
)
SELECT
  created_at,
  payload_json->>'trace_id' AS trace_id,
  payload_json->>'service' AS service,
  payload_json->>'event' AS event,
  COALESCE(
    payload_json->>'cluster_name',
    payload_json->>'cluster',
    payload_json->>'selected_cluster'
  ) AS cluster,
  COALESCE(
    payload_json->>'worker_node',
    payload_json->>'node',
    payload_json->>'selected_node'
  ) AS node,
  CASE
    WHEN payload_json->>'event' = 'global_api.llm.request_completed'
      THEN (payload_json->>'global_total_time_ms')::int
    WHEN payload_json->>'event' = 'global_api.cluster.runtime_data_timing'
      THEN (payload_json->>'total_runtime_data_ms')::int
    WHEN payload_json->>'event' = 'cluster_api.llm.request_succeeded'
      THEN (payload_json->>'cluster_total_time_ms')::int
    ELSE NULL
  END AS step_latency_ms,
  payload_json
FROM app_logs
JOIN params ON true
WHERE config_id = params.config_id
  AND payload_json::jsonb ? 'trace_id'
ORDER BY trace_id, created_at;

-- Use this query to inspect one trace_id end-to-end.
WITH params AS (
  SELECT '2e4168b2-bb0e-4bf3-b8f0-c70c70d6898c'::text AS config_id
)
SELECT
  created_at,
  payload_json->>'trace_id' AS trace_id,
  payload_json->>'service' AS service,
  payload_json->>'event' AS event,
  COALESCE(
    payload_json->>'cluster_name',
    payload_json->>'cluster',
    payload_json->>'selected_cluster'
  ) AS cluster,
  COALESCE(
    payload_json->>'worker_node',
    payload_json->>'node',
    payload_json->>'selected_node'
  ) AS node,
  CASE
    WHEN payload_json->>'event' = 'global_api.llm.request_completed'
      THEN (payload_json->>'global_total_time_ms')::int
    WHEN payload_json->>'event' = 'global_api.cluster.runtime_data_timing'
      THEN (payload_json->>'total_runtime_data_ms')::int
    WHEN payload_json->>'event' = 'cluster_api.llm.request_succeeded'
      THEN (payload_json->>'cluster_total_time_ms')::int
    ELSE NULL
  END AS step_latency_ms,
  payload_json
FROM app_logs
JOIN params ON true
WHERE config_id = params.config_id
  AND payload_json->>'trace_id' = 'REPLACE_WITH_TRACE_ID'
ORDER BY created_at;