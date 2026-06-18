# `src/strato_api/services/start_test.py` — test-runner orchestration & state

This is the heart of the Strato test runner. It owns the **lifecycle state**
(`idle → running → stopping`), validates the config against the global API, and starts the
actual test in a **background thread** so the HTTP request can return immediately. It also
holds the stop mechanism that the workload loop polls.

Three things make this file important to understand:
1. **Module-level global state** guarded by a **lock** (the "only one test at a time" rule).
2. **Threading**: the work runs off the request thread so `/start_test` returns fast.
3. The **two calls to the global API**: one to *validate*, one to *start*.

---

## Imports and module-level state (lines 1–18)

```python
1   import threading
2
3   import requests
4   import uuid
5   from ...models.basemodels import Config
6   from ...db.postgres import save_config
7   from ...custom_logging.logger import set_current_config_id
8   from test.k3d.cluster_configs.test_config import get_test_config
9   from .workload.run_workload import run_workload
10  import structlog
```

- **`threading`** — used to run the test off the request thread, and for the `Lock`.
- **`requests`** — synchronous HTTP client, used to call the global API.
- **`uuid`** — generates the unique `config.id` for this run (line 41).
- **`Config`** — the config model (already validated by FastAPI by the time we get here).
- **`save_config`** — persists the config to Postgres (`db/postgres.py`).
- **`set_current_config_id`** — binds this run's id to **every** log line emitted from now
  on, so logs from one test are groupable (`custom_logging/logger.py`).
- **`get_test_config`** — returns a hard-coded config for the `start_test_test` dev path.
  Note this imports from `test/`, so the production app has a runtime dependency on test
  fixtures. **Minor smell worth flagging.**
- **`run_workload`** — the function that actually drives the questions. Our main jump
  target after this file.
- **`structlog`** — logging.

```python
13  log = structlog.get_logger()
14
15  test_state_lock = threading.Lock()
16  test_running = False
17  stop_requested = False
18  current_config = None
```

- **Line 13** — the logger for this module.
- **Line 15** — a single **mutex**. Because the test runs on a background thread while the
  request thread (and later the stop request, and the status endpoint) read/write the same
  flags, those flags must be protected. Every read or write of the three globals below is
  done while holding this lock.
- **Lines 16–18** — the shared state, the single source of truth for "is a test running":
  - `test_running` — `True` between start and finish.
  - `stop_requested` — set `True` by `stop_test`, polled by the workload loop.
  - `current_config` — the config of the active run (or `None` when idle).

  This is **process-global** state. It implies a hard assumption: **one Strato API process
  runs one test at a time.** If you ran two worker processes, each would have its own copy
  of these flags and the "one test at a time" guarantee would break. Good thing to be able
  to state explicitly in the defense.

---

## `start_test(config)` (lines 21–70) — the request-thread half

This runs **on the HTTP request thread**. It validates, flips the state flags, spawns the
worker thread, and returns. It must be fast.

```python
38      global test_running, stop_requested, current_config
```
- **Line 38** — `global` declares that assignments below rebind the module-level names, not
  create local ones. Needed because we assign to them (lines 62–64).

```python
40      try:
41          config.id = str(uuid.uuid4())
```
- **Line 41** — stamp the config with a fresh unique id. `uuid.uuid4()` is a random UUID;
  `str(...)` makes it a string. This id is the key that ties together the persisted config,
  all the logs, and the results. It's generated **here**, on every start, overwriting
  whatever id came in.

```python
43          # Sanity checks of the config entries
44          ip = config.global_scheduler.ip
45          port = config.global_scheduler.port
46          response = requests.post(
47              f"http://{ip}:{port}/validate_config",
48              json=config.model_dump(),
49              timeout=180
50          )
51          response.raise_for_status()
52          validation = response.json()
53          if not validation["valid"]:
54              raise RuntimeError(f"Invalid config: {validation['errors']}")
55      except Exception as e:
56          raise RuntimeError(f"Validation failed: {str(e)}")
```
- **Lines 44–45** — read the global scheduler's address from the config itself. The config
  tells Strato where the global API lives.
- **Lines 46–50** — POST the whole config to the global API's `/validate_config`.
  `config.model_dump()` turns the Pydantic model into a plain dict for JSON. `timeout=180`
  means "give up after 180s." Why ask the **global** API to validate? Because the global
  API is the one that knows whether the clusters, weights, and runtime data make sense, it
  owns the scheduling domain. Strato deliberately doesn't duplicate that logic. **This is a
  cross-service call; the validation logic lives in the global API**, which we'll reach on
  its own path.
- **Line 51** — `raise_for_status()` throws if the HTTP response was 4xx/5xx.
- **Lines 52–54** — parse the JSON body; if `valid` is false, raise with the returned
  error list.
- **Lines 55–56** — **any** failure here (network error, bad status, invalid config) is
  re-wrapped as a `RuntimeError("Validation failed: ...")`. That `RuntimeError` bubbles up
  to the route, which turns it into HTTP 500. So a config that fails validation never
  starts a test.

```python
58      # Only run one test at a time
59      with test_state_lock:
60          if test_running:
61              raise RuntimeError("A test is already running. Stop the current test before starting a new one.")
62          test_running = True
63          stop_requested = False
64          current_config = config
```
- **Lines 59–64** — the critical section. Holding the lock:
  - if a test is already running, refuse (this becomes the "already running" error).
  - otherwise flip into the running state: `test_running = True`, clear any stale
    `stop_requested`, and record `current_config`.
  - The `with` ensures the lock is released even if line 61 raises.
  - **Why the lock matters:** without it, two near-simultaneous `/start_test` calls could
    both pass the `if test_running` check before either set the flag, and you'd get two
    tests. The lock serializes that check-and-set.

```python
66      # Run the test on a separate thread so the API stays responsive.
67      thread = threading.Thread(target=run_test, args=(config,), daemon=True, name="test-runner")
68      thread.start()
69      log.info("test.started_in_background", config_id=config.id, test_name=config.name)
70      return {"message": f"{config.name} test started successfully"}
```
**This is the only place in the file that creates a thread, and it creates exactly one.**
A "thread" is just an independent line of execution inside the same process; several can
run at once and they share the same memory (which is why the lock and globals exist).

- **Line 67** — this does **not** run anything yet. `threading.Thread(...)` only *builds a
  thread object*: a work order that says "when started, run `run_test`, passing it
  `config`." Nothing executes from it until line 68.
  - `daemon=True` means the thread won't keep the process alive on shutdown; if the main
    process exits, this thread is killed. Acceptable for a test runner.
  - `name="test-runner"` is for log/debug readability.
- **Line 68** — `.start()` actually launches it. From this instant `run_test(config)` is
  running **on a new, separate thread**, in parallel with whatever the current thread does
  next.
- **Lines 69–70** — the current thread logs and **returns the HTTP response immediately**.
  The frontend gets `"<name> test started successfully"` within milliseconds. Returning
  here does **not** stop the background thread, it keeps running `run_test` for minutes
  after this function has returned. **That is the whole point:** a test runs for minutes,
  and an HTTP request can't stay open that long, so we hand the slow work to a background
  thread and free the request immediately. The frontend then polls `GET /test_status` to
  watch progress.

### Wait, which threads exist here?

Only **one** thread is created by our code (line 67–68: the `test-runner`). The other
threads that touch this file's globals are **not created by us**, they belong to the web
server:

- When a request hits `POST /start_test`, the server (uvicorn) is already running
  `start_test` **on one of its own request-handling threads**. Our code runs *on* that
  thread; it didn't create it.
- Later, `POST /stop_test` arrives and the server runs `stop_test` on **another** of its
  request threads.

So the sequence is: the server gives an incoming request a thread → on that thread our
`start_test` spawns **one** extra background thread → then returns, freeing the request
thread. The lock exists precisely because these independent threads (the server's request
threads plus our one background thread) all read and write the same
`test_running` / `stop_requested` / `current_config` variables.

---

## `run_test(config)` (lines 73–128) — the background-thread half

This runs **on the `test-runner` thread**. It does the slow work: persist, tell the global
API to start, then run the workload until it finishes or is stopped.

```python
86      global test_running, stop_requested, current_config
87      try:
88          set_current_config_id(config.id)
89          save_config(config)
90          log.info("test.begins", source="strato_api", config_id=config.id, test_name=config.name)
```
- **Line 88** — bind this run's id into the logging context for this thread, so every later
  log line carries `config_id`. **Jump candidate:** `custom_logging/logger.py`.
- **Line 89** — write the config row to Postgres. This is the **first DB write** in our
  trace. **Jump candidate:** `db/postgres.py:save_config` (and `init_database`, since the
  table it writes to was created there).
- **Line 90** — structured log marking the real start.

```python
92          # Forward start to global API, which configures all clusters.
93          ip = config.global_scheduler.ip
94          port = config.global_scheduler.port
95          url = f"http://{ip}:{port}/start_test"
96
97          log.info("test.forward_to_global", url=url)
98          response = requests.post(url, json=config.model_dump(), timeout=180)
99          response.raise_for_status()
100         log.info("test.global_started", status_code=response.status_code)
```
- **Lines 93–99** — the **second** call to the global API, this time `/start_test`. This is
  what makes the global scheduler configure all the clusters for the run (power up nodes,
  set weights, etc.). Strato is the conductor; the global API does the cluster-side setup.
  **This is the cross-service boundary into `global_api`.** We'll follow it on the global
  API path; for now note it must succeed (`raise_for_status`) before any workload runs.

```python
102         # This blocks inside the background thread until workload ends or stops.
103         results = run_workload(
104             f"http://{ip}:{port}",
105             "/handle_llm_question",
106             config.question,
107             config.start.duration_time_s,
108             config.workload.request_per_minute,
109             config.workload.pattern,
110             config.workload.seed,
111             config.workload.peakiness,
112             stop_check=should_stop_test,
113         )
```
- **Lines 103–113** — run the workload. This **blocks the background thread** for the whole
  duration of the test. The arguments are everything the generator/driver needs:
  - base URL + endpoint path `/handle_llm_question` (the global API's per-question entry).
  - `config.question` — the question configuration.
  - `duration_time_s` — how long to run.
  - `request_per_minute` + `pattern` + `seed` + `peakiness` — the workload shape (steady vs
    peaks, reproducible via the seed).
  - `stop_check=should_stop_test` — a **callback**, not a value. The workload loop calls it
    each iteration to ask "should I stop?" This is how the stop flag reaches the loop
    without sharing globals directly. **Main next jump:** `workload/run_workload.py`.

```python
115         if should_stop_test():
116             log.info("test.stopped", responses=len(results))
117         else:
118             log.info("test.completed", responses=len(results))
119
120     except Exception as e:
121         log.exception("test.failed", error=str(e))
122     finally:
123         # Always reset shared flags so a new test can start cleanly.
124         with test_state_lock:
125             test_running = False
126             stop_requested = False
127             current_config = None
```
- **Lines 115–118** — after the workload returns, decide whether it ended because of a stop
  request or natural completion, and log accordingly. `len(results)` is how many responses
  came back.
- **Lines 120–121** — any failure in the background thread is logged (with traceback via
  `log.exception`). **Crucially, there's no one to re-raise to** — the request already
  returned. So errors here can only be observed in the logs, not in the HTTP response.
  Worth knowing for debugging.
- **Lines 122–127** — the **`finally`** is the safety net: no matter how the run ends
  (success, stop, or crash), reset the three globals back to idle under the lock. This is
  what lets the *next* test start. If this didn't run, `test_running` would be stuck `True`
  and every future `/start_test` would be refused.

---

## Stop mechanism and helpers

### `should_stop_test()` (130–138)
```python
137     with test_state_lock:
138         return stop_requested
```
- A thread-safe read of the stop flag. This is the callback passed into `run_workload`.
  The workload loop calls it each cycle; when it returns `True`, the loop exits. Reading
  under the lock guarantees it sees the value `stop_test` wrote on another thread.

### `stop_test()` (141–163)
```python
154     global stop_requested
155     with test_state_lock:
156         if not test_running:
157             raise RuntimeError("No test is currently running.")
158         stop_requested = True
159         config = current_config
160
161     log.info("test.stop_requested")
162     stop_global_power_scheduler(config.global_scheduler.ip, config.global_scheduler.port)
163     return {"message": "Stop requested"}
```
- Backs `POST /stop_test`. Under the lock: if nothing is running, raise (route maps this
  `RuntimeError` to **409**). Otherwise set `stop_requested = True` and grab the config.
- Note it **copies `current_config` into a local `config` inside the lock** (line 159) and
  uses it *after* releasing the lock (line 162). That's deliberate: it avoids holding the
  lock during a slow network call, while still safely capturing the value. Clean
  concurrency pattern.
- It only *requests* the stop (sets a flag); the workload loop notices on its next poll and
  exits on its own. It does **not** forcibly kill the thread.
- Line 162 also tells the global API to stop its scheduler-side activity.

### `stop_global_power_scheduler(ip, port)` (166–181)
- Best-effort POST to the global API's `/stop_test`. Wrapped so a failure only **warns**
  (line 181), it doesn't raise. The local stop already succeeded; failing to reach the
  global API shouldn't turn into a user-facing error.

### `start_test_test()` (184–191)
- Calls `start_test(get_test_config())`, i.e. starts a run with the hard-coded fixture
  config. Backs the `/start_test_test` dev endpoint.

### `get_test_status()` (194–217)
- Backs `GET /test_status`. Under the lock, returns one of three payloads:
  - not running → `idle`, no id.
  - running **and** `stop_requested` → `stopping`, with the current id.
  - running, not stopping → `running`, with the current id.
- This is exactly the documented `idle → running → stopping` lifecycle, read straight off
  the same flags `start_test`/`run_test`/`stop_test` maintain. The `current_config.id if
  current_config else None` guard avoids a crash if the config was just cleared.

---

## The concurrency model in one picture

Only the **test-runner** thread is created by this file (line 67–68). The other two lanes
are the web server's own request threads, our code just runs on them.

```
[server's request thread]  start_test() ── validate ── flip flags ── spawn thread ── return 200 ✓ done
                                                                          │ creates (only thread we make)
[OUR test-runner thread]              run_test() ── save_config ── tell global API ── run_workload(...) ──┐
                                                                                          ▲ polls         │
[server's request thread]  stop_test() ── set stop_requested ─────────────────────────────┘ should_stop  │
                                                                                                          ▼
                                                        finally: reset flags ── idle again ───────────────┘
```

## Function calls made from this file (jump list)

| Call | Defined in | Status |
|------|-----------|--------|
| `uuid.uuid4()` | stdlib | skip |
| `requests.post(.../validate_config)` | **global_api** route | cross-service, later |
| `set_current_config_id(config.id)` | `custom_logging/logger.py` | **jump soon** |
| `save_config(config)` | `db/postgres.py` | **jump soon** (with `init_database`) |
| `requests.post(.../start_test)` | **global_api** route | cross-service, later |
| `run_workload(...)` | `workload/run_workload.py` | **main next jump** |
| `should_stop_test` (callback) | this file (130) | covered above |
| `get_test_config()` | `test/k3d/.../test_config.py` | dev-only, optional |

**Next jump:** the workload runner, `src/strato_api/services/workload/run_workload.py`,
since that's where the test actually drives questions. (We'll detour into `logger.py` and
`postgres.py` for the two support calls on lines 88–89 when you want; they're small.)
