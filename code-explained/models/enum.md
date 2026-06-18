# `src/models/enum.py` — the `WorkerStatus` lifecycle

One tiny enum, but it's the **node state machine** the whole power story turns on.

```python
class WorkerStatus(str, Enum):
    OFF = "off"
    TURNING_ON = "turning_on"
    TURNING_OFF = "turning_off"
    WORKING = "working"
    IDLE = "idle"
```

- Inherits `str` (`str, Enum`), so each member **is** its string value. That means it serializes
  to plain JSON (`"idle"`) and compares equal to the string, which is why code elsewhere does
  `status == WorkerStatus.IDLE` *and* `n["status"] == WorkerStatus.IDLE.value` interchangeably.

## The five states and who sets them
- **`OFF`** — powered down. Set after SSH shutdown completes; excluded from selection and from
  load.
- **`TURNING_ON`** — GPIO pulse sent, booting. Set by the cluster `turn_on_node`. Not yet usable.
- **`TURNING_OFF`** — shutdown initiated (the 10 s re-check window). Set by `turn_off_node`.
- **`WORKING`** — has in-flight requests. Set by `sync_worker_status` when `inflight > 0`.
- **`IDLE`** — powered on, no in-flight requests. Set when `inflight == 0`.

## Why the distinctions matter
- **Selection** (`choose_worker_node`) only considers `IDLE`/`WORKING` (a node mid-transition
  is skipped).
- **Load** (`get_cluster_runtime_data`) only counts `WORKING`/`IDLE` toward `cluster_load_w`.
- **`sync_worker_status` refuses to touch `OFF`/`TURNING_ON`/`TURNING_OFF`** — those are owned by
  the power scheduler, not by request traffic. This is the boundary between the request path and
  the power path writing the same field.
- **`IDLE` vs `OFF`** is the whole point of the power scheduler: an idle node still draws
  `node_power_idle_w` (1.19 W × scale), so turning idle nodes OFF is where the energy saving
  comes from.

A clean, correct little enum, the only nuance is that the transient states exist precisely so the
two subsystems (requests vs power control) don't clobber each other's view of a node.
