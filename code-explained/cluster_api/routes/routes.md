# `src/cluster_api/routes/routes.py` — Cluster API HTTP endpoints

The cluster API's front door. Same thin-routes pattern. The request our trace follows lands
on **`POST /handle_llm_request`** (89–102). But this file also exposes the endpoints the
**other** parts of the system already called on this cluster earlier in the trace:
- `/set_config` (72–86) — what the global `start_test.py:77` called to push config.
- `/get_cluster_working_nodes` (11–20) — what `cluster_data.py:134` polls every scoring pass.
- the power-control endpoints (`/turn_on_nodes`, `/turn_off_idle_nodes`) — what the **global
  power scheduler** calls to actually execute its decisions.

So this one file is where three threads of the system terminate on the cluster.

---

## Imports (1–8)
```python
2   from ..services.cancel_all_llama_pods import cancel_all_llama_pods
3   from ..services.power_scheduler import change_node_status, turn_off_idle_nodes
4   from ..services.llm import handle_llm
5   from ...models.basemodels import ClusterInformation, QuestionConfig
6   from ...custom_logging.logger import set_current_config_id
7   from ..util.cluster_config import config_store
```
- **`handle_llm`** (4) — backs `/handle_llm_request`, our next jump.
- **`change_node_status`, `turn_off_idle_nodes`** (3) — the **cluster-side power scheduler**
  (the local execution half of your power-scheduler component). Called by the power-control
  endpoints below.
- **`config_store`** (7) — this cluster's **own** in-memory store (`util/cluster_config.py`),
  distinct from the global API's.

---

## `POST /handle_llm_request` (89–102) — where the global API's forward lands
```python
89  @router.post("/handle_llm_request")
90  def handle_llm_request_endpoint(question: QuestionConfig, request: Request):
101     trace_id = request.headers.get("X-Trace-Id")
102     return handle_llm(question, trace_id=trace_id)
```
- Same structure as the global API's `/handle_llm_question`: parse the `QuestionConfig` body,
  read the **`X-Trace-Id`** header (line 101), delegate to the service. This is the **third
  pickup** of that trace id (Strato set it → global re-read it → cluster re-reads it now), so
  the cluster's `RequestLog` carries the same id and the whole hop chain is correlatable.
- Delegates to `handle_llm(question, trace_id=...)`. **Next jump:** `services/llm.py`.
- Like the global route, **no try/except** here, errors propagate to FastAPI's default 500,
  which the global API's inner `except` (lines 110–139 there) then records and re-raises.

---

## The endpoints the rest of the system calls on this cluster

These complete the file and are the receiving ends of calls already in the trace:

- **`GET /get_cluster_working_nodes` (11–20)** — returns `config_store.get_worker_nodes_dict()`,
  the current node list with status/slot counts. **This is what `cluster_data.py:135` calls
  for every cluster on every scoring pass** to count active/idle nodes. So each scored
  question pings this on each cluster.
- **`POST /set_config` (72–86)** — **what the global `start_test.py:77` called.** Takes the
  `ClusterInformation`, binds the config id into logging (83), stores it (84), and
  **`build_worker_nodes()`** (85) constructs this cluster's `WorkerNode` list from the config.
  This is how a cluster API learns which nodes it owns at the start of a run. Returns the
  stored config.
- **`POST /turn_on_nodes/` (23–34)** and **`POST /turn_off_idle_nodes/` (54–69)** — the
  **execution endpoints the global power scheduler calls.** `turn_on_nodes` → `change_node_status(n, "on")`;
  `turn_off_idle_nodes(idle_time, stay_one)` → the idle-shutdown logic. The `stay_one=True`
  default (61–63) is the **keeper invariant** at the API boundary: always keep one node alive.
  These are the cluster-local half of your power-scheduler story (the global tier *decides
  how many*, these endpoints *do it*).
- **`POST /turn_off_nodes/` (37–51)** — manual/debug force-off by count. Docstring explicitly
  says **not used in production** (41–42); it's a testing affordance.
- **`GET /get_cluster_information` (105–113)** — returns the full in-memory `ClusterInformation`
  (what `all_configuration.get_cluster_information` on the global side fetches).
- **`POST /cancel_all_llama_pods` (116–125)** — deletes all llama pods so K3s restarts them
  cleanly; a reset/recovery affordance. Touches Kubernetes directly (`cancel_all_llama_pods`).

---

## Recap and next jump

- The global API's forwarded question lands on `handle_llm_request_endpoint` (90), which
  re-reads the trace id and delegates to `handle_llm`.
- The same file is where `/set_config` (run setup), `/get_cluster_working_nodes` (polled by
  scoring), and the power-control endpoints (driven by the global power scheduler) terminate,
  three other parts of the system you've already seen calling *in*.

**Next jump:** `src/cluster_api/services/llm.py` — `handle_llm(...)`. This is the cluster's
node-selection logic (slot-aware pick), the forward to the chosen node's `llama-server`, and
the queue-vs-inference timing split that the global API logged.
