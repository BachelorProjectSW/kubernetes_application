-- Power decision timeline (global + cluster + request outcomes)
-- Replace config_id in params before running.
WITH params AS (
  SELECT 'c97c493c-889e-4380-b3b3-e527e76cbdac'::text AS config_id
),
terminal_events AS (
  SELECT
    l.created_at,
    l.log_type,
    COALESCE(l.payload_json->>'event', l.terminal_debug) AS event,
    COALESCE(
      l.payload_json->>'cluster_name',
      l.payload_json->>'cluster',
      l.payload_json->>'selected_cluster'
    ) AS cluster,
    COALESCE(
      l.payload_json->>'worker_node',
      l.payload_json->>'node',
      l.payload_json->>'selected_node'
    ) AS node,
    l.payload_json
  FROM app_logs l
  JOIN params p ON l.config_id = p.config_id
  WHERE l.payload_json IS NOT NULL
    AND (
      COALESCE(l.payload_json->>'event', '') LIKE 'global_api.power.%'
      OR COALESCE(l.payload_json->>'event', '') LIKE 'cluster_api.power.%'
      OR COALESCE(l.payload_json->>'event', '') IN (
        'global_api.llm.cluster_attempt_failed',
        'cluster_api.llm.no_available_worker',
        'cluster_api.llm.request_failed'
      )
    )
),
node_status_events AS (
  SELECT
    l.created_at,
    l.log_type,
    'node_status_snapshot'::text AS event,
    l.payload_json->>'cluster' AS cluster,
    l.payload_json->>'node' AS node,
    l.payload_json
  FROM app_logs l
  JOIN params p ON l.config_id = p.config_id
  WHERE l.log_type = 'NodeStatusLog'
)
SELECT
  e.created_at,
  e.log_type,
  e.event,
  e.cluster,
  e.node,
  -- Key metrics for quick scanning
  e.payload_json->>'nodes_to_add' AS nodes_to_add,
  e.payload_json->>'nodes_remaining_to_add' AS nodes_remaining_to_add,
  e.payload_json->>'requested' AS requested,
  e.payload_json->>'turned_on' AS turned_on,
  e.payload_json->>'idle_time_s' AS idle_time_s,
  e.payload_json->>'last_request_age_s' AS last_request_age_s,
  e.payload_json->>'inflight_requests' AS inflight_requests,
  e.payload_json->>'error' AS error,
  e.payload_json
FROM (
  SELECT * FROM terminal_events
  UNION ALL
  SELECT * FROM node_status_events
) e
ORDER BY e.created_at;

-- Optional aggregate: count power errors by cluster
-- WITH params AS (
--   SELECT 'c97c493c-889e-4380-b3b3-e527e76cbdac'::text AS config_id
-- )
-- SELECT
--   COALESCE(payload_json->>'cluster_name', payload_json->>'cluster') AS cluster,
--   payload_json->>'event' AS event,
--   COUNT(*) AS count
-- FROM app_logs
-- JOIN params ON config_id = params.config_id
-- WHERE payload_json->>'event' LIKE '%failed%'
-- GROUP BY cluster, event
-- ORDER BY count DESC;
