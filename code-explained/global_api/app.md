# `src/global_api/app.py` — Global API entry point

The request that left Strato on `run_workload.py:121` arrives **here**, at the global
scheduler process. This is a *separate* process (often on a different machine) from Strato,
with its own memory, its own DB engine, and its own logging globals. The only thing tying
the two together is the HTTP call and the `X-Trace-Id` header.

This entry point is the **same shape** as Strato's `app.py`, just leaner. Compare:

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
14      port = int(os.environ.get("PORT", "8020"))
15      uvicorn.run(app, host="0.0.0.0", port=port)
```

Line by line, with only the differences from Strato's `app.py` called out (the rest is
identical and already explained in `strato_api/app.md`):

- **Lines 1–5** — same imports as Strato, **minus** `CORSMiddleware`. The global API is
  **not called by a browser**, only by other backend services (Strato, and itself), so it
  doesn't need CORS headers. The frontend never talks to it directly. That's the one
  structural difference.
- **Line 7** — `app = FastAPI()`, the application object, created at import time.
- **Line 9** — `app.include_router(router)` mounts the endpoints from `routes/routes.py`,
  including `/handle_llm_question`. Same mechanism as Strato.
- **Line 11** — `init_database()`. Note this is the **same `init_database`** function, from
  the same `src/db/postgres.py` we already documented. Because the global API is a separate
  process, it runs its own table-creation at startup. In practice the tables already exist
  (Strato made them), so this is a no-op idempotent check, but it makes the global API able
  to stand up independently. The global API and Strato **share one Postgres database**;
  they're separate *processes* pointed at the *same* DB.
- **Lines 13–15** — the run guard. Default port **`8020`** (vs Strato's `8090`), bound to
  `0.0.0.0` so the other services on the Tailscale network can reach it. `uvicorn.run`
  blocks and serves.

## What's different about this service, conceptually

Strato is the *conductor* (owns the test lifecycle and drives the workload). The global API
is the *scheduler*: for each incoming question it gathers live per-cluster data, scores the
clusters, picks one, and forwards the question. It also runs the **power scheduler** loop in
the background. So unlike Strato, this process has real domain logic, and it's where **your
two components** (cluster selection + power scheduler) live.

One thing to watch for as we go deeper: the global API holds **in-memory runtime state**
about clusters and nodes (loaded from the config at `start_test`), the same single-process
assumption applies, one global API process per deployment.

## Function calls from this file (jump list)

| Call | Defined in | Status |
|------|-----------|--------|
| `app.include_router(router)` | `global_api/routes/routes.py` | **next** |
| `init_database()` | `src/db/postgres.py` | already documented |
| `uvicorn.run(...)` | library | skip |

**Next jump:** `src/global_api/routes/routes.py`, the `/handle_llm_question` handler, which
is exactly where Strato's POST lands.
