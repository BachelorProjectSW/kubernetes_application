# `src/strato_api/services/workload/run_workload.py` — driving the questions

This is where the test actually *happens*: it builds a schedule of request times, then fires
HTTP requests at the global API's `/handle_llm_question` at those times, collecting a result
per request. It's the file `run_test` blocks on (line 103).

The whole file is built on **asyncio**, Python's single-threaded concurrency model. That's a
different mechanism from the *threads* in `start_test.py`, and the distinction matters, so
the first section below explains it before the line-by-line.

> Reading order in the file is "bottom function first": `run_workload` (the sync entry, 249)
> calls `execute_workload` (the async engine, 22), which calls `generate_workload` (the
> schedule, in `generator.py`). I'll follow **execution order**: `run_workload` →
> `execute_workload` → the per-request coroutine.

---

## First: threads vs asyncio (why two different things)

In `start_test.py` we used a **thread** to run the workload off the request thread. Inside
that one background thread, this file now uses **asyncio** to run *hundreds of requests
concurrently* without making hundreds of threads.

- A **thread** is a separate line of execution the OS schedules; good for "do this whole job
  in the background."
- **asyncio** is *cooperative* concurrency on a **single thread**: tasks run one at a time,
  but whenever a task hits an `await` on something slow (like waiting for an HTTP response),
  it *voluntarily yields* control so another task can run. While 200 requests are all
  "waiting for the server to answer," one thread can manage all 200, because waiting is the
  only thing they're doing.
- This fits perfectly here: sending an LLM question is **I/O-bound** (you fire it and wait
  seconds for the answer). You don't need 200 threads to wait; you need one thread that
  juggles 200 in-flight waits. That's exactly what `async`/`await` gives us.

Key vocabulary used below:
- **coroutine**: a function defined with `async def`. Calling it doesn't run it; it returns
  an object you must `await` or schedule.
- **`await x`**: "pause here until `x` finishes, and let other tasks run meanwhile."
- **task**: a coroutine scheduled to run concurrently (via `asyncio.create_task`). Creating
  the tasks is what lets them all be in flight at once.
- **event loop**: the scheduler that runs the tasks and resumes them when their awaited
  work is ready. `asyncio.run(...)` starts one.

---

## Imports and constants (1–19)

```python
1   import asyncio
2   import time
3   import aiohttp
4   import json
5   import requests
6   import structlog
7   import uuid
8   from aiohttp import ClientConnectorError
9   from .generator import generate_workload
10  from ....custom_logging.logger import log_request, log_sent
11  from ....models.basemodels import QuestionConfig
```
- **`asyncio`** — the event loop / concurrency machinery.
- **`time`** — `time.perf_counter()`, a high-resolution monotonic clock used for scheduling
  and measuring latency (monotonic = never goes backwards, unaffected by clock changes; the
  right clock for measuring durations).
- **`aiohttp`** — the **async** HTTP client (you can't use the blocking `requests` inside an
  async task without stalling the loop). Note both are imported: `aiohttp` for the
  concurrent request firing, `requests` only for the one-off blocking stop call at the end.
- **`json`** — to serialize the question payload manually (line 101).
- **`uuid`** — generates the per-request `trace_id` that's propagated across all three
  services.
- **`ClientConnectorError`** (line 8) — the specific aiohttp exception for "couldn't even
  establish the TCP connection," used to decide what's retryable.
- **`generate_workload`** (line 9) — builds the list of request timestamps. **Next jump
  after this file.**
- **`log_request`, `log_sent`** (line 10) — the telemetry helpers from `logger.py` we
  already documented.
- **`QuestionConfig`** — the typed question payload.

```python
18  RETRY_DELAY_S = 2
19  MAX_RETRIES = 2
```
- Retry policy constants: wait 2s between retries, retry at most twice. Used only for
  **connection** failures (see line 119/137).

---

## `run_workload(...)` (249–285) — the sync→async bridge (executed first)

This is the function `run_test` actually calls. It's an ordinary (synchronous) function
whose whole job is to start an event loop, run the async engine inside it, and guarantee the
global stop call afterward.

```python
280     try:
281         return asyncio.run(
282             execute_workload(host, endpoint, question, duration_s, rpm, pattern, seed, peakiness, stop_check)
283         )
284     finally:
285         _stop_global_test(host)
```
- **Line 282** — `execute_workload(...)` is a coroutine; *calling it here does not run it*,
  it just creates the coroutine object. **`asyncio.run(...)`** (line 281) is what creates an
  event loop, runs that coroutine to completion, and returns its result (the list of
  per-request results). `asyncio.run` **blocks** until everything is done, which is why this
  call blocks the background thread back in `run_test`.
- **Lines 284–285** — the `finally` guarantees that **no matter how the workload ends**
  (completed, stopped, or crashed), we tell the global API to stop. This is belt-and-braces
  alongside the stop path in `start_test.py`: when the workload finishes naturally, the
  global scheduler still needs to be told the test is over so it stops powering nodes, etc.
- This is the textbook pattern for calling async code from a sync caller: one `asyncio.run`
  at the boundary.

---

## `execute_workload(...)` (22–228) — the async engine

This is the big coroutine. Structure: generate the schedule → set up an HTTP session →
define a per-request coroutine → launch one task per request → poll for stop while they run
→ gather results.

### Setup and schedule generation (54–71)
```python
54      request_timeout_s = 1000
55      start_time = time.perf_counter()
57      timestamps = generate_workload(
58          duration_s=duration_s, rpm=rpm, pattern=pattern, seed=seed, peakiness=peakiness,
63      )
```
- **Line 54** — per-request timeout of **1000 seconds**. That's deliberately huge: an LLM
  answer on a Raspberry-Pi-class node can take a very long time, and we'd rather wait than
  falsely record a timeout. (Contrast with the 3s *connect* timeout below, two different
  things.)
- **Line 55** — record `start_time` as the zero point. Every scheduled timestamp is an
  *offset from this moment*.
- **Lines 57–63** — `generate_workload` returns a **list of timestamps** (offsets in
  seconds), one per request, shaped by the pattern (steady vs peaks), rate, and seed. The
  seed makes it reproducible, the same config produces the same schedule every run, which is
  what makes test runs comparable. **This is our next jump:** `generator.py`.

### HTTP session configuration (73–80)
```python
74      timeout = aiohttp.ClientTimeout(total=request_timeout_s, sock_connect=3)
78      connector = aiohttp.TCPConnector(force_close=True)
80      async with aiohttp.ClientSession(base_url=host, timeout=timeout, connector=connector) as session:
```
- **Line 74** — two timeouts in one: `total=1000s` (whole request) and **`sock_connect=3`**
  (you must establish the TCP connection within 3 seconds). So a dead/unreachable host fails
  fast (3s), but a slow *answer* is tolerated (1000s). This split is what makes the retry
  logic meaningful, a connect failure is retryable, a slow inference is not.
- **Line 78** — `force_close=True` means **a fresh TCP connection per request**, no
  keep-alive pooling (comment on 76–77). Why: the global scheduler may route different
  requests to different clusters; reusing a pooled connection could pin traffic or mask
  per-request routing. A new connection per request keeps each request independent and the
  measurements clean. (Trade-off: more connection overhead, accepted here for correctness.)
- **Line 80** — open one `ClientSession` for the whole workload (`base_url=host` so each
  request only needs the endpoint path). The `async with` guarantees the session is closed
  at the end.

### The per-request coroutine `_send_request(ts)` (82–206)

Defined **inside** `execute_workload` so it closes over `session`, `start_time`, `question`,
etc. One of these runs per scheduled request.

```python
93      delay = ts - (time.perf_counter() - start_time)
94      if delay > 0:
95          await asyncio.sleep(delay)
```
- **Lines 93–95 are the scheduler.** `ts` is when this request *should* fire (offset from
  start). `(time.perf_counter() - start_time)` is how long we've actually been running.
  Their difference is how much longer to wait. If positive, `await asyncio.sleep(delay)`
  pauses *just this task* until its moment, while letting every other task run. This is how
  hundreds of tasks each fire at their own planned time off a single thread. If `delay <= 0`
  (we're already behind schedule), it skips the sleep and fires immediately.

```python
99      trace_id = str(uuid.uuid4())
100     request_start = time.perf_counter()
101     payload_json = json.dumps(question.model_dump())
102     headers = {"Content-Type": "application/json", "X-Trace-Id": trace_id}
```
- **Line 99** — a unique `trace_id` for this request. This is the **correlation id** that
  travels through global → cluster → llama (via the `X-Trace-Id` header on line 104) and
  ties together all the logs for this one question. Distinct from the run-wide `config_id`.
- **Line 100** — start the latency clock for *this* request.
- **Line 101** — serialize the question to a JSON string once.
- **Line 102** — headers, including the trace id.

```python
114     try:
115         log_sent(host, trace_id=trace_id, payload={"question": question.question})
116     except Exception:
117         pass
```
- **Lines 114–117** — record the **dispatch moment** via `log_sent` (the `LogSent` row from
  `logger.py`). The comment (113) says why: the **global power scheduler reads these to
  compute requests-per-second** (the λ in your throughput model). Wrapped in a bare
  try/except that swallows everything, telemetry must never break the actual request. (A
  bare `except: pass` is a code smell in general, but justified here as "logging is
  best-effort.")

```python
119     for attempt in range(MAX_RETRIES + 1):
120         try:
121             async with session.post(endpoint, data=payload_json, headers=headers) as resp:
122                 request_reached_host = True
123                 body = await resp.text()
124                 duration_ms = int((time.perf_counter() - request_start) * 1000)
131                 return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body}
133         except (asyncio.TimeoutError, ClientConnectorError):
137             if request_reached_host or attempt == MAX_RETRIES:
138                 raise
144             await asyncio.sleep(RETRY_DELAY_S)
```
- **Line 119** — up to `MAX_RETRIES + 1 = 3` attempts.
- **Line 121** — **the actual HTTP POST to the global API's `/handle_llm_question`**. This is
  the **cross-service call** that leaves Strato and enters the global scheduler, the heart of
  the whole request flow. `await ... session.post(...)` yields until the response arrives.
- **Line 122** — the instant the POST returns, mark `request_reached_host = True`. This flag
  is the linchpin of the retry safety logic.
- **Line 123** — `await resp.text()` reads the body (also async).
- **Line 124** — compute this request's latency in ms.
- **Line 131** — return a result dict; `ok` is true for 2xx status.
- **Lines 133–144 — the retry rule, and it's careful:** only `TimeoutError` /
  `ClientConnectorError` (connection-level failures) are caught. The guard on 137 says: if
  we **already reached the host** (`request_reached_host`) *or* we're out of attempts, give
  up (`raise`). The reason (comment 135–136) is important and correct: **if the server might
  have already received the POST, retrying could double-process the question.** So it only
  retries failures that happened *before* the request landed (pure connection failures).
  This is idempotency-aware retrying, a genuinely good detail to highlight.

```python
145     except asyncio.CancelledError:
146         log.info("workload.request_cancelled")
147         return {"ok": False, "error": "cancelled"}
```
- Cancellation (from a stop request, see the polling loop) surfaces here as
  `CancelledError`; return a clean "cancelled" result rather than blowing up.

```python
148     except asyncio.TimeoutError:        # (and the analogous except Exception on 177)
150         if not request_reached_host:
151             log_request(cluster_name="unknown", ... success=False, ... trace_id=trace_id)
170         log.warning("strato.workload.request_timeout", ...)
176         return {"ok": False, "error": ...}
```
- **Lines 148–206** — the two terminal failure handlers (a timeout-specific one and a
  catch-all `except Exception`). They're nearly identical. The notable logic is line 150 /
  179: **only log a failed `RequestLog` if the request never reached the host.** Why: if it
  *did* reach the host, the **global/cluster side already logged its own `RequestLog`** for
  this `trace_id`, logging another here would double-count. So Strato only records the
  failure for requests that died before arriving (cluster/load/carbon all `0`, cluster
  "unknown"). This keeps the request-count telemetry honest, and it's the same
  no-double-counting instinct as the retry rule.

### Launch, stop-polling, and gather (208–228)
```python
209     tasks = [asyncio.create_task(_send_request(ts)) for ts in timestamps]
```
- **Line 209 is where concurrency actually starts.** `asyncio.create_task` schedules each
  `_send_request` coroutine to run on the event loop **immediately and concurrently**. After
  this line all requests are "in flight" as tasks (each currently sleeping until its `ts`).
  One list comprehension = the entire workload launched.

```python
212     while not all(t.done() for t in tasks):
213         if stop_check():
214             log.info("workload.stop_requested - cancelling all tasks")
216             for t in tasks:
217                 if not t.done():
218                     t.cancel()
219             break
220         await asyncio.sleep(0.5)
```
- **Lines 212–220 — the stop watcher.** While not all tasks are done, every 0.5s it calls
  `stop_check()`, which is `should_stop_test` from `start_test.py`, the callback that reads
  the global stop flag. If a stop was requested, it **cancels every unfinished task** (line
  218, which is what raises `CancelledError` inside them) and breaks. This is the mechanism
  that makes `/stop_test` actually halt an in-progress workload promptly (within ~0.5s)
  instead of waiting for all requests to finish. The `await asyncio.sleep(0.5)` both paces
  the poll and yields control so the request tasks can run.

```python
222     results = await asyncio.gather(*tasks, return_exceptions=True)
224     results = [r for r in results if isinstance(r, dict)]
225     success_count = sum(1 for r in results if r.get("ok"))
227     log.info("strato.workload.completed", success_count=..., failure_count=...)
228     return results
```
- **Line 222** — `asyncio.gather` waits for **all** tasks and collects their return values
  into a list (in task order). `return_exceptions=True` means if a task raised instead of
  returning, the exception object is put in the list *instead of* propagating, so one failed
  request can't abort the gather.
- **Line 224** — filter to only dict results, dropping any raised-exception entries that
  slipped through (the cancelled/failed tasks that returned non-dicts or raised).
- **Lines 225–228** — tally successes/failures, log a summary, return the results list. This
  list is what `run_test` receives as `results` and counts with `len(results)`.

---

## `_stop_global_test(host)` (231–246)

```python
242     response = requests.post(f"{host}/stop_test", timeout=500)
243     response.raise_for_status()
245  except Exception as e:
246     log.warning("strato.workload.global_stop_failed", error=str(e))
```
- A **blocking** `requests` POST (not aiohttp, because we're back in sync land, called from
  `run_workload`'s `finally` *after* `asyncio.run` returned). Tells the global API the test
  is over. Best-effort: any failure only warns. This is the call guaranteed by the `finally`
  on line 285.

---

## The shape of one run, end to end

```
run_test (thread) ─calls→ run_workload (sync)
                            └ asyncio.run → execute_workload (async)
                                 ├ generate_workload() → [t0, t1, t2, ...]   ← schedule
                                 ├ create_task(_send_request) per timestamp  ← all in flight
                                 │     each: sleep until its ts → log_sent → POST /handle_llm_question
                                 │           → (retry connect failures only) → return result
                                 ├ poll stop_check() every 0.5s → cancel all if stop
                                 └ gather → results list
                            └ finally: _stop_global_test(host)
```

## Function calls made from this file (jump list)

| Call | Defined in | Status |
|------|-----------|--------|
| `generate_workload(...)` | `workload/generator.py` | **next jump** |
| `log_sent(...)`, `log_request(...)` | `custom_logging/logger.py` | done |
| `session.post(endpoint, ...)` → `/handle_llm_question` | **global_api** | cross-service, the main boundary |
| `_stop_global_test` → `requests.post(/stop_test)` | **global_api** | cross-service |
| `asyncio.*`, `aiohttp.*`, `requests.*` | libraries | skip |

## Things to flag for your defense
- **Two concurrency models, on purpose:** one background *thread* (so the HTTP request
  returns) containing an *asyncio* loop (so hundreds of I/O-bound requests run on one
  thread). Be ready to articulate why asyncio and not more threads: the work is waiting on
  the network, not burning CPU.
- **Idempotency-aware retries:** only connection failures are retried, and never once the
  request has reached the host, to avoid double-processing a question.
- **No double-counting of telemetry:** Strato only logs a failed `RequestLog` when the
  request never reached the host; otherwise the global/cluster side owns that log.
- **`force_close=True`** (new connection per request) is a deliberate measurement-cleanliness
  choice, worth knowing if asked about performance.
- **1000s request timeout vs 3s connect timeout** is the key to telling "host is down" apart
  from "answer is just slow."

**Next jump:** `src/strato_api/services/workload/generator.py` — `generate_workload(...)`,
the schedule builder (steady vs peaks, the sine-superposition peak model, the seed). This is
the workload-shape math from your report's workload-generator section.
