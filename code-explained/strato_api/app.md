# `src/strato_api/app.py` — Strato API entry point

This is the file that runs when you start the Strato API (`python -m src.strato_api.app`).
It is the **entry point of the whole test harness**: the Strato VM sits next to Postgres,
owns the test runner, and serves results to the frontend. Everything else in our deep dive
flows out of here.

There is no `start_test` logic in this file. This file only does three things: build the
FastAPI app, attach the routes, and create the database tables. Then it waits for HTTP
requests. The actual `start_test` work lives in `routes/routes.py`, which is where we go
next.

---

## Line by line

```python
1  from fastapi import FastAPI
2  from fastapi.middleware.cors import CORSMiddleware
3  from .routes.routes import router
4  from ..db.postgres import init_database
5  import os
6  import uvicorn
```

- **Line 1** — `FastAPI` is the web-framework class. Calling `FastAPI()` gives us the
  application object that holds all the routes and middleware.
- **Line 2** — `CORSMiddleware` is FastAPI's built-in Cross-Origin Resource Sharing
  handler. CORS is a browser security rule: by default a webpage served from origin A
  (the frontend, e.g. `:8091`) is **not allowed** to call an API on origin B (this API,
  `:8090`). This middleware adds the response headers that tell the browser "it's fine,
  let this through." Without it, the React frontend's `fetch` calls would be blocked by
  the browser.
- **Line 3** — imports `router`, the object that bundles all of this service's HTTP
  endpoints (defined in `routes/routes.py`). The leading `.` is a **relative import**:
  "from the `routes` package next to me." This matches our project convention of relative
  imports inside `src/`.
- **Line 4** — imports `init_database`, the function that creates the Postgres tables.
  The `..` means "go up one package level" (from `strato_api` up to `src`) and into `db`.
- **Line 5** — `os`, used once below to read the `PORT` environment variable.
- **Line 6** — `uvicorn`, the ASGI server that actually runs the FastAPI app (FastAPI is
  just the framework; uvicorn is the process that listens on the socket).

```python
8  app = FastAPI()
```

- **Line 8** — creates the application instance. This single `app` object is what uvicorn
  serves and what we attach middleware and routes to. Note this runs at **import time**:
  the moment this module is imported, `app` exists. That matters because uvicorn imports
  the module to get at `app`.

```python
11  app.add_middleware(
12      CORSMiddleware,
13      allow_origins=["*"],
14      allow_credentials=True,
15      allow_methods=["*"],
16      allow_headers=["*"],
17  )
```

- **Lines 11–17** — register the CORS middleware on the app. Middleware wraps every
  request/response.
  - `allow_origins=["*"]` — accept calls from **any** origin. The comment on line 10
    explains why this is acceptable here: everything is hosted on the private Tailscale
    network, so there is no hostile public traffic to defend against. In a public
    deployment this wildcard would be a security smell, but on a closed VPN it is fine.
  - `allow_credentials=True` — allow cookies / auth headers to be sent on cross-origin
    requests. (Strictly, the CORS spec forbids combining `allow_credentials=True` with
    `allow_origins=["*"]`; browsers will reflect the origin instead. In practice we don't
    rely on credentials here, so it doesn't bite us. **Worth flagging as a minor
    inconsistency** if anyone asks.)
  - `allow_methods=["*"]` — allow GET, POST, etc., all HTTP verbs.
  - `allow_headers=["*"]` — allow any request header (e.g. our custom `X-Trace-Id`).

```python
19  app.include_router(router)
```

- **Line 19** — mounts every endpoint defined in `routes/routes.py` onto the app. After
  this line, paths like `/start_test`, `/stop_test`, `/get_results` actually exist on the
  server. This is the **first function call** in our chain: `include_router` pulls in the
  router object whose definition we will read next.

```python
22  init_database()
```

- **Line 22** — creates the Postgres tables (`configs` and `app_logs`) if they don't
  already exist. This is a **function call at startup**, so strictly it's the first thing
  we "jump to." It lives in `src/db/postgres.py`. It runs at **module import time** (not
  inside `if __name__ == "__main__"`), which means the tables are ensured to exist no
  matter how the module is loaded, including when imported by tests or by uvicorn's
  reloader. We will cover `init_database` and the rest of `postgres.py` when the
  `start_test` path first touches the database (it persists the config almost
  immediately), so the DB layer is explained right where we first use it.

```python
24  if __name__ == "__main__":
25      port = int(os.environ.get("PORT", "8090"))
26      uvicorn.run(app, host="0.0.0.0", port=port)
```

- **Line 24** — the standard Python guard. This block runs **only** when the file is
  executed directly (`python -m src.strato_api.app`), not when it's merely imported. So
  in tests, importing `app` gives you the configured application object **without**
  starting a server.
- **Line 25** — read the port from the `PORT` environment variable, defaulting to
  `8090` (the Strato API's documented port). `os.environ.get("PORT", "8090")` returns a
  string, so `int(...)` converts it to a number for uvicorn.
- **Line 26** — start the server. `host="0.0.0.0"` binds to **all** network interfaces
  (not just localhost), so other machines on the Tailscale network (the frontend, the
  global API) can reach it. `uvicorn.run` blocks here forever, serving requests until the
  process is killed.

---

## What happens, in order, when this file runs

1. Python imports the module → `app = FastAPI()` is created.
2. CORS middleware is attached.
3. `app.include_router(router)` registers all endpoints.
4. `init_database()` ensures the Postgres tables exist.
5. If run as `__main__`, `uvicorn.run(...)` starts listening on `:8090` and blocks.
6. The server now sits idle until a request arrives. The frontend hitting
   **`POST /start_test`** is what kicks off everything else.

## Function calls made from this file (our "jump" list)

| Call | Where it's defined | When we cover it |
|------|--------------------|------------------|
| `FastAPI()` | external library | not ours, skip |
| `app.add_middleware(...)` | external library | not ours, skip |
| `app.include_router(router)` | `routes/routes.py` (the `router` object) | **next** |
| `init_database()` | `src/db/postgres.py` | when `start_test` first uses the DB |
| `uvicorn.run(...)` | external library | not ours, skip |

**Next jump:** `src/strato_api/routes/routes.py`, specifically the `start_test` endpoint,
since that is the request the frontend sends to begin a test run.
