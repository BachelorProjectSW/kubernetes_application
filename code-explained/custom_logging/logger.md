# `src/custom_logging/logger.py` — structured logging + run tagging

We arrived here from `run_test` line 88: `set_current_config_id(config.id)`. That's the
function our trace needs, but the file does three jobs, so it's worth understanding whole:

1. **Run tagging** — `set_current_config_id` / `_current_config_id`: stamp every log with
   the active test's id so logs from one run can be grouped.
2. **structlog configuration** — the `structlog.configure(...)` block sets up *how* every
   log line in the entire codebase is formatted, filtered, and optionally saved to the DB.
3. **Typed log helpers** — `log_request`, `log_sent`, `log_node_status_snapshot`: convenience
   functions that build a structured log model and persist it. These are used by the
   global/cluster APIs, not on the Strato `start_test` path, but they round-trip through the
   same DB layer (`save_model_log`) we'll meet next.

The CLAUDE.md summary of this file: *"`logger.py` wraps structlog. `set_current_config_id`
attaches the active config id to every log, which is how logs from one test run are
grouped."*

---

## Imports and module state (lines 1–18)

```python
1   import structlog
2   from datetime import datetime, timezone
3   from typing import TypeVar
4   from .models.log_models import NodeStatusLog, RequestLog, LogSent
5   from ..models.basemodels import WorkerNode
6   from ..db.postgres import (
7       save_model_log,
8       save_terminal_debug,
9   )
10  import os
```
- **`structlog`** — the structured-logging library this module wraps. Unlike plain
  `logging`, structlog emits key/value pairs (e.g. `config_id=...`, `latency_ms=...`)
  instead of just a string, which is what makes logs queryable.
- **`datetime, timezone`** — to timestamp log entries in UTC.
- **`TypeVar`** — used to declare `T` on line 67 (a generic type var; see note there).
- **Line 4** — the three structured log models (`NodeStatusLog`, `RequestLog`, `LogSent`)
  built by the helper functions below. They live in `models/log_models.py`.
- **Line 5** — `WorkerNode`, needed by `log_node_status_snapshot`'s signature.
- **Lines 6–9** — `save_model_log` and `save_terminal_debug` from the DB layer. This is the
  bridge: logging optionally **writes to Postgres**, not just stdout. Both go to the
  `app_logs` table.
- **`os`** — to read the `LOG_LEVEL` / `SAVE_LOGS_IN_DB` environment variables.

```python
12  log = structlog.get_logger()
14  # Change the level of logging set to DEBUG for all, info (exclude debug etc...)
15  LOG_LEVEL = os.getenv("LOG_LEVEL", "CRITICAL").upper()
16  # whether the debug, info, error, warning logs should be saved in the DB or just printed.
17  SAVE_LOGS_IN_DB = os.getenv("SAVE_LOGS_IN_DB", "FALSE").upper() == "TRUE"
18  _LOGGER_CONFIG_ID: str | None = None
```
- **Line 12** — the module's own logger.
- **Line 15** — the minimum level that gets emitted, from env, **defaulting to
  `CRITICAL`**. This is a big deal: with the default, almost all `log.info` / `log.debug`
  / `log.warning` calls across the whole codebase are **silently dropped**. To actually see
  logs you must set `LOG_LEVEL=DEBUG` (or `INFO`). Worth knowing when debugging: "why am I
  seeing no logs" is usually this default. **Flag for your defense:** the production default
  is deliberately near-silent.
- **Line 17** — whether logs are also persisted to Postgres, default `FALSE`. Note the
  comparison: env value upper-cased must equal `"TRUE"`. So only the literal string
  `TRUE`/`true` turns it on.
- **Line 18** — the module-level global holding the current run id. `str | None`, starts
  `None` (no run active). This is the single piece of mutable state the next two functions
  read/write.

---

## `set_current_config_id` (21–28) — our call

```python
21  def set_current_config_id(config_id: str | None):
27      global _LOGGER_CONFIG_ID
28      _LOGGER_CONFIG_ID = config_id
```
- This is the line `run_test` calls. It just stores the run id in the module global
  `_LOGGER_CONFIG_ID`. The `global` keyword is needed so the assignment rebinds the
  module-level name rather than making a local.
- After this call, **every log line emitted anywhere in this process** can be tagged with
  this id (via `_current_config_id()` below, used inside the structlog processor and the DB
  helpers). Passing `None` clears it (done at the end of a run).
- **Important caveat (same shape as the test-state globals):** this is **process-global**,
  not per-thread or per-request. In the Strato API that's fine because one process runs one
  test at a time. But note: the global API and cluster API are *separate processes* with
  their *own* copy of this global, so the id has to be propagated across services another
  way, that's what the `X-Trace-Id` header does. The config-id global only groups logs
  *within* one process.

## `_current_config_id` (31–36)
```python
36      return _LOGGER_CONFIG_ID
```
- Trivial getter for the global. Leading underscore = "private to this module." Used by the
  structlog processor (line 47) and by the helper functions (lines 120, 142, 165) to tag/
  persist with the active run id.

---

## `_get_terminal_logs` processor (39–50)

```python
39  def _get_terminal_logs(_, __, event_dict):
45      level = str(event_dict.get("level", "info"))
46      message = str(event_dict.get("event", ""))
47      config_id = _current_config_id()
48      if SAVE_LOGS_IN_DB:
49          save_terminal_debug(config_id, message, level, dict(event_dict))
50      return event_dict
```
- This is a **structlog processor**: a function structlog calls for *every* log event as it
  passes through the pipeline. Its signature is fixed by structlog: `(logger, method_name,
  event_dict)`. The first two are ignored here (named `_`, `__`).
- `event_dict` is the accumulated key/value payload of the log line. `event` is the message
  string; `level` was added by an earlier processor.
- **Lines 48–49** — *if* DB-saving is on, persist this terminal/debug line to Postgres via
  `save_terminal_debug`, tagged with the current run id. This is how human-readable log
  strings end up in the `app_logs` table alongside the structured models.
- **Line 50** — a processor **must return the event_dict** so the next processor in the
  chain (the console renderer) can use it. This one's side effect is the DB save; it doesn't
  modify the dict.

---

## `structlog.configure(...)` (53–64) — the global logging setup

This runs **at import time** and configures logging for the *whole codebase* (any module
that does `structlog.get_logger()` inherits this).

```python
54      processors=[
55          structlog.processors.add_log_level,
56          structlog.processors.TimeStamper(fmt="iso"),
57          _get_terminal_logs,
58          structlog.dev.ConsoleRenderer(),
59      ],
```
- The **processor chain**, applied in order to every log event:
  1. `add_log_level` — adds the `level` key (info/debug/...).
  2. `TimeStamper(fmt="iso")` — adds an ISO-8601 timestamp.
  3. `_get_terminal_logs` — our custom processor: optional DB save (above).
  4. `ConsoleRenderer()` — renders the final dict as the pretty, colored console line you
     see in the terminal. It's last because it turns the dict into a string.

```python
60      wrapper_class=structlog.make_filtering_bound_logger(LOG_LEVEL),
61      context_class=dict,
62      logger_factory=structlog.PrintLoggerFactory(),
63      cache_logger_on_first_use=True,
```
- **Line 60** — apply the `LOG_LEVEL` filter (the `CRITICAL` default from line 15). This is
  *where* sub-critical logs get dropped: the filtering bound logger short-circuits anything
  below the threshold **before** the processors run.
- **Line 61** — context stored as a plain `dict`.
- **Line 62** — `PrintLoggerFactory` means the final rendered line is written with `print`
  (to stdout). Simple; fine for containers where stdout is captured.
- **Line 63** — cache the configured logger the first time each module asks for one (a
  performance optimization; it also means config changes after first use won't apply).

---

## `T = TypeVar("T")` (67)
- Declares a generic type variable. It's **not actually used** by any function below (the
  helpers have concrete types). Looks like a leftover from a removed generic helper.
  **Minor dead code worth noting.**

---

## The typed log helpers (70–168) — used by other services, same DB sink

These three aren't on the Strato `start_test` path (they're called from the global and
cluster APIs while serving requests), but they all follow the **same pattern**, so once you
see one you know all three:

> build a structured log model → `save_model_log(_current_config_id(), entry)` inside a
> try/except that only **warns** on DB failure → also emit a `log.debug` to console.

The try/except-warn is deliberate: **a logging/DB hiccup must never crash the request it's
logging about.** That's why every save is wrapped and downgraded to a warning.

### `log_request(...)` (70–124)
- The big one: records a **completed inference request** with all timing + energy fields
  (latency, queue time, inference time, cluster load, renewable fraction, blended carbon and
  cost, the question/answer, status code, trace id). This is the `RequestLog` that the
  scoring/results analysis later reads back. Builds a `RequestLog` (96–115), rounds the
  numeric fields for storage, dumps to a JSON-safe dict (117), saves (120), warns on failure
  (122), console-debugs (124). This is the per-request telemetry row behind the whole
  results dashboard.
- Note the many `cluster_*` / `global_*` timing fields: they're what let the report split
  end-to-end latency into queue time vs inference time, the exact distinction that matters
  for your power-scheduler latency discussion.

### `log_sent(...)` (127–147)
- Records the **dispatch moment** (before the response arrives): a `LogSent` with cluster +
  `trace_id` + payload. Correlating a `LogSent` with its later `RequestLog` by `trace_id`
  gives total latency, and counting `LogSent` timestamps gives requests-per-second.

### `log_node_status_snapshot(...)` (150–167)
- Records a **worker node's state** (idle/working/offline) at a moment, as a `NodeStatusLog`.
  Used to reconstruct, after a run, when nodes powered on/off, directly relevant to the
  power-scheduler story.

---

## Recap and next jump

- `set_current_config_id(config.id)` simply parked the run id in a module global so
  subsequent logs (and DB saves) are tagged with it.
- The file also globally configures structlog (note the near-silent `CRITICAL` default) and
  defines the typed telemetry helpers that the other services use, all of which persist via
  the DB layer.

Every "save" in this file (`save_terminal_debug`, `save_model_log`) lands in the DB layer,
which is exactly where `run_test`'s **next** call goes too: line 89, `save_config(config)`.

**Next jump:** `src/db/postgres.py` — `save_config`, plus `init_database` (the table
creation from `app.py`) and the `save_model_log` / `save_terminal_debug` sinks referenced
here, since they're all in that one file.
