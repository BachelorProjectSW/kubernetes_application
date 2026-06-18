# `src/cluster_api/app.py` — Cluster API entry point (third tier)

The request the global API forwarded on `handle_llm_request.py:111` arrives **here**, at a
**cluster API** instance. There is **one of these per K3s cluster**, and (unlike Strato and
the global API) in production it runs **as a pod inside its own cluster** (deployed via
`src/cluster_api/manifest/`). Its job: know its own worker nodes, pick one, forward the
question to that node's `llama-server` pod, and expose endpoints to power nodes on/off.

The entry point is **byte-for-byte the same shape** as the global API's `app.py`, only the
port differs:

```python
1   from fastapi import FastAPI
2   from .routes.routes import router
3   from ..db.postgres import init_database
4   import os
5   import uvicorn
7   app = FastAPI()
9   app.include_router(router)
11  init_database()
13  if __name__ == "__main__":
14      port = int(os.environ.get("PORT", "8040"))
15      uvicorn.run(app, host="0.0.0.0", port=port)
```

- **Lines 1–9** — same as before: build the app, mount the router. No CORS (not browser-facing).
- **Line 11** — `init_database()` again. Each cluster API is a **separate process** with its
  own startup, but pointed at the **same shared Postgres** (so its `RequestLog`s land in the
  same `app_logs` table, grouped by the same `config_id`). Idempotent table check.
- **Lines 13–15** — default port **`8040`** (Strato 8090, global 8020, cluster 8040), bound
  to `0.0.0.0`. In the k3d test harness this runs as a local uvicorn process; in production
  it's the pod's container process.

## What's conceptually different about this tier

- It is **cluster-local**: it only knows *its own* nodes (loaded via `/set_config`), not the
  whole fleet. The global API is the only component with the cross-cluster view.
- It does the **node-level** work the global tier doesn't: slot-aware node selection
  (`WorkerNode.active_requests / queued_requests / free_slots`), forwarding to a specific
  `llama-server`, and the **physical power control** (GPIO power-on, SSH shutdown) that's the
  hardware half of your power-scheduler story.
- It holds its **own in-memory config store** (`util/cluster_config.py`), separate from the
  global API's `config_store`. Same name, different class, different process.

## Function calls from this file (jump list)

| Call | Defined in | Status |
|------|-----------|--------|
| `app.include_router(router)` | `cluster_api/routes/routes.py` | **next** |
| `init_database()` | `db/postgres.py` | done |
| `uvicorn.run(...)` | library | skip |

**Next jump:** `src/cluster_api/routes/routes.py`, the `/handle_llm_request` handler, where
the global API's forwarded question lands.
