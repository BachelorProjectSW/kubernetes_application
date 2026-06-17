# `src/strato_api/routes/routes.py` — Strato API HTTP endpoints

This is the **HTTP layer** of the Strato API. Its only job is to map URLs to service
functions: take the incoming request, hand it to the right function in `services/`, and
translate any error into an HTTP status code. There is no business logic here on purpose,
that lives in `services/`. This is the standard FastAPI "thin routes, fat services"
split, and our whole codebase follows it (`app.py` → `routes/routes.py` → `services/`).

Our path through the program enters at **`POST /start_test`** (lines 9–29).

---

## Imports (lines 1–6)

```python
1  from fastapi import APIRouter, HTTPException
2  from ..services.start_test import start_test, start_test_test, stop_test, get_test_status
3  from ..services.test_results import get_test_results
4  from ...models.basemodels import Config
5  from ...db.postgres import read_all_configs
6  router = APIRouter()
```

- **Line 1** — `APIRouter` is FastAPI's way to group endpoints in a sub-module instead of
  defining them all on the `app` object directly. `HTTPException` is what we `raise` to
  return a specific HTTP error code (e.g. 500) to the caller.
- **Line 2** — pulls in the four service functions that back the test-runner endpoints.
  `start_test` is the one our path follows. The `..` climbs from `routes` up to
  `strato_api`, then into `services/start_test.py`.
- **Line 3** — `get_test_results` backs the results endpoint (frontend reads this after a
  run).
- **Line 4** — `Config`, the top-level Pydantic model from `src/models/basemodels.py`. It
  is the entire test configuration. Declaring an endpoint parameter as type `Config` is
  what makes FastAPI **validate and parse** the incoming JSON body for us.
- **Line 5** — `read_all_configs`, a DB helper used by `/get_configs`.
- **Line 6** — create the `router`. This is the exact object that `app.py` line 19
  (`app.include_router(router)`) mounted onto the application. So importing this module is
  what populates `router` with all the `@router.post(...)` endpoints below.

---

## `POST /start_test` (lines 9–29) — our entry point

```python
9   @router.post("/start_test")
10  def start_test_endpoint(config: Config):
```

- **Line 9** — the decorator registers this function as the handler for `POST /start_test`.
  FastAPI now routes any POST to that URL here.
- **Line 10** — the handler. The parameter `config: Config` is the key line: because the
  type is the `Config` Pydantic model, FastAPI:
  1. reads the JSON body of the request,
  2. validates it against the `Config` schema (every sub-object: `StartConfig`,
     `WeightsConfig`, the cluster list, etc.),
  3. if validation fails, **automatically** returns a 422 with a detailed error before our
     code ever runs,
  4. if it passes, hands us a fully typed `Config` object.
  So by the time we're inside the function body, `config` is guaranteed well-formed. This
  is why there is no manual parsing here.

- **Lines 11–25** — the docstring. Ruff's `D` rules make docstrings on public functions
  mandatory, and the whole repo uses Google-style. It documents Args/Returns/Raises.

```python
26      try:
27          return start_test(config)
28      except Exception as e:
29          raise HTTPException(status_code=500, detail=str(e))
```

- **Line 26–27** — call the service function `start_test(config)` and return whatever it
  returns straight back to the caller as the JSON response. **This is our next jump:**
  `services/start_test.py:start_test`.
- **Line 28–29** — if anything inside `start_test` raises, catch it and convert it to an
  HTTP **500** with the exception text as the detail. This is the thin-route pattern:
  the route doesn't *handle* errors, it just translates exceptions into HTTP status codes
  so the frontend gets a clean response instead of a raw stack trace.

---

## The other endpoints (not on our path, summarized)

These exist on the same router but our `start_test` trace doesn't go through them. Quick
tour so the file is fully accounted for:

- **`POST /start_test_test` (32–49)** — starts a hard-coded test scenario with **no
  request body**. A convenience/dev endpoint that calls `start_test_test()` instead of
  needing a full `Config`. Same 500-on-error wrapper.
- **`POST /stop_test` (52–69)** — calls `stop_test()` to stop a running test. Note it has
  **two** except clauses: a `RuntimeError` maps to **409 Conflict** (used when stopping
  conflicts with the current state, e.g. nothing is running), and any other exception maps
  to 500. This is the lifecycle's `running → stopping` trigger.
- **`GET /test_status` (72–81)** — returns the runner's current state (`idle` / `running`
  / `stopping`). No try/except because `get_test_status()` just reads an in-memory value
  and can't meaningfully fail.
- **`GET /test_results` (84–105)** — takes a `config_id` **query parameter** (it's a plain
  `str` argument, not a Pydantic body, so FastAPI reads it from the query string) and
  returns stored results for that run. Note the `except HTTPException: raise` on line 101:
  it lets HTTP errors raised *inside* the service pass through unchanged (so a 404 stays a
  404) and only wraps *unexpected* errors as 500. The `print(e)` on line 104 is a debug
  leftover, it logs to stdout rather than through our structlog logger. **Minor
  inconsistency worth noting** (everything else logs via the custom logger).
- **`GET /get_configs` (108–125)** — returns every saved config. Line 121 calls
  `read_all_configs()` and serializes each with `.model_dump(mode="json")`
  (`mode="json"` makes types like datetimes JSON-safe). Same selective HTTP-passthrough
  pattern.

---

## Recap and next jump

- The frontend POSTs the `Config` JSON to `/start_test`.
- FastAPI validates it into a `Config` object.
- `start_test_endpoint` calls `start_test(config)` and returns its result, wrapping any
  failure as HTTP 500.

**Next jump:** `src/strato_api/services/start_test.py`, the `start_test` function.
