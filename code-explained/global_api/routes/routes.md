# `src/global_api/routes/routes.py` — Global API HTTP endpoints

This is the global scheduler's thin HTTP layer, same "thin routes, fat services" pattern as
Strato. The endpoint our trace lands on is **`POST /handle_llm_question`** (lines 25–41),
the one each workload request hits.

This file also exposes the two endpoints Strato called earlier in our trace from the *other*
direction: `/validate_config` (called from `start_test.py:46`) and `/start_test` (called
from `run_test:98`). So this single file is the global API's entire front door.

---

## Imports (1–8)

```python
1   from fastapi import APIRouter, HTTPException, Request
3   from ..services.validate_config import validate_config
4   from ..services.get_all_worker_nodes import get_all_worker_nodes
5   from ..services.handle_llm_request import handle_llm_request
6   from ..services.start_test import start_test, stop_test
7   from ...models.basemodels import Config, QuestionConfig
8   router = APIRouter()
```
- **`Request`** (line 1) — new here vs Strato's routes: FastAPI's raw request object, needed
  to read the `X-Trace-Id` **header** (Pydantic body parsing doesn't give you headers).
- **Lines 3–6** — the four service functions backing the endpoints. `handle_llm_request`
  (line 5) is the one our trace follows.
- **Line 7** — `Config` and `QuestionConfig` models. `QuestionConfig` is the body type for
  `/handle_llm_question`; it's the **same model** Strato serialized and sent on the wire, so
  FastAPI re-parses the JSON back into a `QuestionConfig` here.
- **Line 8** — the `router` that `app.py:9` mounted.

---

## `POST /handle_llm_question` (25–41) — where Strato's request lands

```python
25  @router.post("/handle_llm_question")
26  def handle_llm_question(question: QuestionConfig, request: Request):
40      trace_id = request.headers.get("X-Trace-Id")
41      return handle_llm_request(question, trace_id=trace_id)
```
- **Line 26** — two parameters, and the distinction matters:
  - `question: QuestionConfig` — FastAPI parses the **JSON body** into this model
    (validation included), the question Strato sent.
  - `request: Request` — the raw request, injected by FastAPI when you type-annotate a
    parameter as `Request`. We need it only to read a header.
- **Line 40** — pull the **`X-Trace-Id`** header that Strato set on `run_workload.py:104`.
  `.get(...)` returns `None` if absent (so a manual curl without the header still works). This
  is the moment the trace id **crosses the process boundary**: Strato generated it, put it on
  the wire, and the global API now picks it back up so its own logs carry the same id. This is
  the entire mechanism behind "correlate logs across services."
- **Line 41** — hand off to the service function `handle_llm_request(question, trace_id=...)`
  and return whatever it returns straight to Strato as the JSON response. **This is our next
  jump:** `services/handle_llm_request.py`.
- **Note:** unlike Strato's `/start_test`, this handler has **no try/except wrapper**. Any
  exception inside `handle_llm_request` propagates to FastAPI's default handler, which
  returns a 500. (Back on the Strato side, `_send_request`'s `except Exception` then records
  the failed request.) Worth knowing: error handling for the per-question path lives *inside*
  the service, not at this route.

---

## The other endpoints (the rest of the front door)

These complete the file. Two of them we already saw Strato *call* earlier in the trace,
now you see the receiving end.

- **`GET /get_all_clusters_working_nodes` (11–22)** — returns every worker node available
  for scheduling, via `get_all_worker_nodes()`. Diagnostics/dashboard use; not on the
  request path.
- **`POST /start_test` (44–61)** — **this is what `run_test:98` called.** Takes the full
  `Config`, calls `start_test(config)` to configure all clusters for the run (load runtime
  state, power up nodes, start the power-scheduler loop). Wraps failures as 500. We'll
  document `services/start_test.py` on the global side, since it's what sets up the in-memory
  cluster state the scheduler later reads.
- **`POST /stop_test` (64–72)** — **what `_stop_global_test` and `stop_global_power_scheduler`
  called.** Calls `stop_test()` to tear down scheduler-side activity. No try/except, default
  500 on error.
- **`POST /validate_config` (75–89)** — **what `start_test.py:46` called first.** Runs
  `validate_config(config)` and returns the `{valid, errors}` result Strato checked. This is
  the validation Strato deliberately delegates to the global API because the global API owns
  the scheduling domain.

So three of this file's five endpoints are the receiving ends of calls already in our trace
(`validate_config`, `start_test`, `stop_test`), and `handle_llm_question` is the live
per-request path.

---

## Recap and next jump

- Strato's per-question POST lands on `handle_llm_question` (26).
- The handler extracts the `X-Trace-Id` header (40), re-picking-up the correlation id across
  the process boundary, and delegates to `handle_llm_request` (41).
- Error handling for this path lives inside the service, not the route.

**Next jump:** `src/global_api/services/handle_llm_request.py` — `handle_llm_request(...)`.
This is the top of the scheduling logic: it gathers per-cluster data, calls scoring to pick
a cluster (**your cluster-selection component**), and forwards the question to that cluster's
API. From here we're inside the parts you present.
