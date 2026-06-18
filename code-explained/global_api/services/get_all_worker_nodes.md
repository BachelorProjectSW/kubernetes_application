# `src/global_api/services/get_all_worker_nodes.py` — fleet-wide node list

Small aggregator. Backs `GET /get_all_clusters_working_nodes` (diagnostics/dashboard). Not on the
request path.

`get_all_worker_nodes()` (9–57):
- If no active config → warn and return `[]`.
- For each cluster (`config_store.get_clusters()`), GET its `/get_cluster_working_nodes` and
  **extend** one flat list with the returned nodes.
- **Resilient by design (docstring + code):** a failed or non-list response from one cluster is
  logged and **skipped**, you get whatever the reachable clusters returned, never an exception.
  So a single down cluster doesn't blank the whole view.

That's it: a fault-tolerant "give me every node across the fleet" helper. Same per-cluster HTTP
fan-out pattern as `cluster_data` and `power_scheduler`, just aggregating instead of scoring.

## Defense-worthy point
- Demonstrates the consistent **fault-tolerant aggregation** style: gather what you can, log the
  rest, never fail the whole call for one bad cluster.
