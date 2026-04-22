WITH params AS (
  SELECT '0b6a31ac-6365-4ba2-bde3-21af8f58cb07'::text AS config_id
)
SELECT
  payload_json->>'cluster_name' AS cluster,
  payload_json->>'worker_node' AS node,
  COUNT(*) AS request_count,
  AVG((payload_json->>'cluster_llama_inference_ms')::int) AS avg_inference_ms,
  MIN((payload_json->>'cluster_llama_inference_ms')::int) AS min_inference_ms,
  MAX((payload_json->>'cluster_llama_inference_ms')::int) AS max_inference_ms,
  PERCENTILE_CONT(0.50) WITHIN GROUP (
    ORDER BY (payload_json->>'cluster_llama_inference_ms')::int
  ) AS p50_inference_ms,
  PERCENTILE_CONT(0.95) WITHIN GROUP (
    ORDER BY (payload_json->>'cluster_llama_inference_ms')::int
  ) AS p95_inference_ms
FROM app_logs
JOIN params ON true
WHERE app_logs.config_id = params.config_id
  AND payload_json->>'event' = 'cluster_api.llm.request_succeeded'
  AND payload_json->>'service' = 'cluster_api'
GROUP BY cluster, node
ORDER BY avg_inference_ms DESC;