/* =========================================================
   TEMPLATE find everytime a specific log is places
   ========================================================= */
SELECT * 
FROM app_logs WHERE config_id = 'INSERT_ID' 
WHERE terminal_debug == 'INSERT_LOG_NAME'
ORDER BY created_at ASC;

/* =========================================================
   TEMPLATE  find errors
   ========================================================= */
SELECT * 
FROM app_logs WHERE config_id = 'INSERT_ID' 
WHERE log_type == 'error' or log_type == 'warning'
ORDER BY created_at ASC;


/* =========================================================
   PARAMS (edit these values first)
   ========================================================= */
WITH params AS (
  SELECT
    'REPLACE_WITH_CONFIG_ID'::text AS config_id,
    'REPLACE_WITH_TRACE_ID_OR_EMPTY'::text AS trace_id,
)

/* =========================================================
   TEMPLATE Recent events for one config (chronological)
   ========================================================= */
SELECT
  l.created_at,
  l.config_id,
  l.payload_json->>'service' AS service,
  l.payload_json->>'event' AS event,
  l.payload_json->>'trace_id' AS trace_id,
  l.payload_json
FROM app_logs l
JOIN params p ON l.config_id = p.config_id
ORDER BY l.created_at ASC;


/* =========================================================
   TEMPLATE  Trace a single request across services
   ========================================================= */
WITH params AS (
  SELECT
    'REPLACE_WITH_CONFIG_ID'::text AS config_id,
    'REPLACE_WITH_TRACE_ID'::text AS trace_id
)
SELECT
  l.created_at,
  l.payload_json->>'service' AS service,
  l.payload_json->>'event' AS event,
  l.payload_json->>'trace_id' AS trace_id,
  l.payload_json
FROM app_logs l
JOIN params p ON l.config_id = p.config_id
WHERE l.payload_json->>'trace_id' = p.trace_id
ORDER BY l.created_at ASC;

