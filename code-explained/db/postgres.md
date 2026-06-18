# `src/db/postgres.py` — the entire persistence layer

This one file is the **whole database layer** for all three services. Everything that's
saved or read (configs, request logs, node-status snapshots, terminal logs) goes through
here. It uses **SQLModel** (Pydantic + SQLAlchemy) on top of Postgres.

We reach it from two places already in our trace:
- `app.py` line 22 called **`init_database()`** at startup (table creation).
- `run_test` line 89 calls **`save_config(config)`** (the first row written for a run).
- and `logger.py` routes its saves through **`save_model_log`** / **`save_terminal_debug`**.

So this file ties together everything we've seen. There are only **two tables** (per
CLAUDE.md): `configs` (one row per saved `Config`) and `app_logs` (one generic JSON row for
every structured/terminal log). All the structured log models round-trip through `app_logs`.

---

## Imports and module setup (1–21)

```python
1   from __future__ import annotations
3   import os
4   import threading
5   from datetime import datetime, timezone
6   from typing import Any, TypeVar
7   import structlog
9   from pydantic import BaseModel
10  from fastapi.encoders import jsonable_encoder
11  from sqlalchemy import JSON, Column, Text, create_engine, text
12  from sqlalchemy.engine import URL, make_url
13  from sqlmodel import Field, SQLModel, Session, select
15  from ..custom_logging.models.log_models import NodeStatusLog
18  from ..models.basemodels import Config
20  TModel = TypeVar("TModel", bound=BaseModel)
21  log = structlog.get_logger()
```
- **Line 1** — `from __future__ import annotations` makes all type hints lazy (stored as
  strings). It avoids import-order problems and lets you write `int | None` style hints
  freely. Standard at the top of modules with lots of typing.
- **`threading`** — for the lock guarding the engine singleton (line 104).
- **`jsonable_encoder`** (line 10) — FastAPI helper that turns arbitrary Python objects
  (datetimes, Pydantic models, etc.) into JSON-safe primitives. Used in
  `save_terminal_debug` to sanitize a free-form payload.
- **Line 11** — SQLAlchemy bits: `JSON`/`Text` column types, `Column` to customize a
  column, `create_engine` to make the DB engine, `text` for raw SQL.
- **Line 12** — `URL`/`make_url` to parse and manipulate a connection URL (used to swap the
  database name when creating the DB).
- **Line 13** — SQLModel: `Field` (column definition), `SQLModel` (base class for table
  models), `Session` (a unit of work / transaction), `select` (query builder).
- **Line 20** — `TModel` is a **generic type variable bound to `BaseModel`**. It lets
  `read_model_logs` say "I take a model *class* and return a list of *that same* model,"
  so the caller gets correctly-typed results.

---

## Connection URL helpers (24–75)

### `_database_url()` (24–43)
```python
34      url = os.getenv("DATABASE_URL")
35      if url:
36          return url
38      host = os.getenv("POSTGRES_HOST", "100.109.95.2")  # Strato IP
39      port = os.getenv("POSTGRES_PORT", "5433")
40      user = os.getenv("POSTGRES_USER", "strato")
41      password = os.getenv("POSTGRES_PASSWORD", "strato")
42      db_name = os.getenv("POSTGRES_DB", "strato")
43      return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"
```
- Builds the DB connection string. **Priority:** if `DATABASE_URL` is set, use it verbatim
  (line 34–36). Otherwise assemble one from individual `POSTGRES_*` vars, with the project
  defaults documented in CLAUDE.md: host `100.109.95.2` (the Strato Tailscale IP), port
  `5433`, and user/pass/db all `strato`.
- `postgresql+psycopg://` — the `+psycopg` part picks the psycopg (v3) driver.
- **Security note for the defense:** the default password is hard-coded as `strato`. Fine
  for a closed Tailscale lab network, not for anything public.

### `_admin_url(url)` (46–57)
```python
56      admin_db = os.getenv("POSTGRES_ADMIN_DB", "postgres")
57      return url.set(database=admin_db)
```
- Takes the app URL and returns the same URL pointed at the **admin** database (default
  `postgres`). Why: you can't create database `strato` while connected *to* `strato`, you
  connect to the always-present `postgres` database to issue `CREATE DATABASE`. `url.set(...)`
  returns a new URL with just the database name swapped.

### `_db_name(url)` (60–75)
```python
73      if not url.database:
74          raise ValueError("DATABASE_URL must include a database name")
75      return url.database
```
- Pulls the database name out of the parsed URL, raising if it's missing. Used by
  `_ensure_database_exists` to know which DB to look for / create.

---

## The two table models (78–101)

These classes **define the database schema**. `table=True` makes SQLModel create a real
table for them; `SQLModel.metadata.create_all` (in `init_database`) reads these class
definitions to emit `CREATE TABLE`.

### `ConfigRecord` → table `configs` (78–87)
```python
83      id: int | None = Field(default=None, primary_key=True)
84      config_id: str = Field(index=True)
85      config_name: str | None = Field(default=None, index=True)
86      config_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
87      created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
```
- `id` — auto-increment integer primary key (DB-internal row id).
- `config_id` — our UUID string (the `config.id` from `start_test`), **indexed** because we
  look configs up by it constantly.
- `config_name` — human-readable name, indexed, nullable.
- `config_json` — the **entire `Config` object** stored as a JSON column. This is the
  important design choice: rather than a column per config field, the whole config is dumped
  to one JSON blob. Flexible (config shape can change without a migration), at the cost of
  not being able to query *inside* the config in SQL.
- `created_at` — UTC timestamp, defaulted at insert time via `default_factory`.

### `AppLogRecord` → table `app_logs` (90–100)
```python
95      id: int | None = Field(default=None, primary_key=True)
96      config_id: str | None = Field(default=None, index=True)
97      log_type: str = Field(index=True)
98      payload_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
99      terminal_debug: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
100     created_at: datetime = Field(...)
```
- This is the **one generic log table** for everything. The trick is `log_type` (line 97):
  it stores *which kind* of log this row is, the model class name (`"RequestLog"`,
  `"NodeStatusLog"`, `"LogSent"`) or a terminal level (`"info"`, `"warning"`).
- `config_id` — groups all logs of one run (indexed).
- `payload_json` — the structured log model dumped to JSON (for model logs), or the
  context dict (for terminal logs).
- `terminal_debug` — the human-readable message string for terminal logs; `None` for
  structured model logs. So a row is *either* a structured log (payload, no message) *or* a
  terminal log (message + payload). This dual-purpose design is why `save_model_log` sets
  `terminal_debug=None` and `save_terminal_debug` fills it in.

---

## The engine singleton (103–129)

```python
103 _ENGINE = None
104 _ENGINE_LOCK = threading.Lock()
107 def _engine():
124     global _ENGINE
125     if _ENGINE is None:
126         with _ENGINE_LOCK:
127             if _ENGINE is None:  # re-check after acquiring lock
128                 _ENGINE = create_engine(_database_url(), pool_pre_ping=True)
129     return _ENGINE
```
- The **engine** is the object that manages a pool of DB connections, created once and
  reused. Creating it is expensive, so it's a lazy singleton.
- **Lines 125–128 are the classic "double-checked locking" pattern**, and it's the same
  shape as the thread story from `start_test.py`:
  1. quick check `if _ENGINE is None` *without* the lock (fast path once it exists),
  2. only if it looks unset, take the lock,
  3. **re-check** inside the lock (line 127) because another thread might have created it
     while we waited for the lock,
  4. create it only if still none.
  Without the re-check, two threads racing at startup could each build an engine. This is
  why the lock exists, multiple request threads / background threads all call `_engine()`.
- `pool_pre_ping=True` — before handing out a pooled connection, ping it; if it's gone
  stale (DB restarted, network dropped), discard and make a fresh one. Prevents "server
  closed the connection" errors on idle pools. (Note: recent commit history mentions a
  `noCache`/no-cache change; `pool_pre_ping` is the connection-liveness safeguard here.)

---

## `_ensure_database_exists()` (132–149) and `init_database()` (152–161)

### `_ensure_database_exists` (132–149)
```python
138     url = make_url(_database_url())
139     database_name = _db_name(url)
140     admin_engine = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)
142     with admin_engine.connect() as conn:
143         exists = conn.execute(
144             text("SELECT 1 FROM pg_database WHERE datname = :name"),
145             {"name": database_name},
146         ).scalar_one_or_none()
148         if exists is None:
149             conn.execute(text(f'CREATE DATABASE "{database_name}"'))
```
- Makes sure the **database itself** exists (not the tables, the database). Connects to the
  admin DB, queries Postgres's `pg_database` catalog for our DB name, and if it's missing,
  issues `CREATE DATABASE`.
- `isolation_level="AUTOCOMMIT"` (line 140) is required: `CREATE DATABASE` **cannot run
  inside a transaction** in Postgres, so the connection must auto-commit each statement.
- `scalar_one_or_none()` returns the single value (`1`) if the row exists, else `None`.
- The query uses a **bound parameter** `:name` (safe), but line 149 uses an **f-string** to
  inject the database name directly into the SQL. That's technically SQL-injectable, but the
  name comes from our own config/env, not user input, so it's not a live risk. Worth noting
  for completeness.

### `init_database` (152–161) — called from `app.py`
```python
158     log.info("db.init_database.start")
159     _ensure_database_exists()
160     SQLModel.metadata.create_all(_engine())
161     log.info("db.init_database.done")
```
- The startup entry point. Two steps: ensure the DB exists (159), then **create all
  tables** (160). `SQLModel.metadata.create_all` looks at every `table=True` class
  (`ConfigRecord`, `AppLogRecord`) and runs `CREATE TABLE IF NOT EXISTS` for each, so it's
  **idempotent**, safe to call on every startup (the docstring says exactly this).
- This is why `app.py` can blindly call `init_database()` at import time: if the tables
  already exist, nothing happens; if not, they're created.

---

## `save_config(config)` (164–180) — our call from `run_test`

```python
171     payload = config.model_dump(mode="python")
172     row = ConfigRecord(
173         config_id=config.id,
174         config_name=config.name,
175         config_json=payload,
176     )
177     with Session(_engine()) as session:
178         session.add(row)
179         session.commit()
180     log.info("db.save_config", config_id=config.id, config_name=config.name)
```
- **Line 171** — serialize the whole `Config` to a dict. `mode="python"` keeps Python types
  (e.g. real `datetime` objects) rather than JSON strings; SQLModel's JSON column handles the
  final JSON conversion on write.
- **Lines 172–176** — build the row: the UUID, the name, and the whole config blob.
- **Lines 177–179** — the standard write pattern used everywhere in this file:
  - `Session(_engine())` opens a transaction-scoped session (the `with` guarantees it's
    closed).
  - `session.add(row)` stages the insert.
  - `session.commit()` flushes it to Postgres and commits the transaction.
- **Line 180** — log success with the ids.
- This is the **first row written for a run**: it persists the exact config so results can
  later be tied back to the settings that produced them.

---

## The log sinks (183–222) — called from `logger.py`

### `save_model_log(config_id, log_model)` (183–200)
```python
191     row = AppLogRecord(
192         config_id=config_id,
193         log_type=type(log_model).__name__,
194         payload_json=log_model.model_dump(mode="json"),
195         terminal_debug=None,
196     )
197     with Session(_engine()) as session:
198         session.add(row); session.commit()
```
- Persists any structured log model into `app_logs`. The clever bit is line 193:
  `type(log_model).__name__` becomes the `log_type` string (`"RequestLog"`, etc.), so one
  table holds many log kinds. `terminal_debug=None` marks it as a structured (not terminal)
  row. Same add/commit pattern.

### `save_terminal_debug(config_id, message, level, payload)` (203–222)
```python
213     safe_payload = jsonable_encoder(payload)
214     row = AppLogRecord(
215         config_id=config_id,
216         log_type=level,
217         payload_json=safe_payload,
218         terminal_debug=message,
219     )
```
- The sink for human-readable terminal logs (called by the `_get_terminal_logs` processor
  in `logger.py`). Here `log_type` is the **level** (`info`/`warning`/...) and
  `terminal_debug` holds the actual message. `jsonable_encoder` (line 213) is needed because
  the structlog `event_dict` can contain arbitrary non-JSON objects; this flattens them to
  JSON-safe values first.

---

## The read side (225–367) — used later, by results & scheduling

Not on the write path, but this is how everything saved above is read back. All follow the
SQLModel `select(...).where(...)` pattern inside a `Session`.

- **`read_model_logs(log_model_class, config_id?, since?)` (225–262)** — the generic reader.
  Filters `app_logs` by `log_type == log_model_class.__name__` (plus optional config and
  time bounds), orders by time, and **reconstructs each JSON payload back into the Pydantic
  model** (line 255: `log_model_class(**row.payload_json)`). The generic `TModel` typing
  means if you pass `RequestLog`, you get `list[RequestLog]`. **This is the function the
  global scheduler uses to pull recent latency logs** for scoring, so it matters to your
  components.
- **`read_latest_node_status_log(config_id, cluster, node)` (265–311)** — finds the most
  recent `NodeStatusLog` for a specific node. It pulls **all** node-status rows newest-first
  (line 283 `.desc()`) and scans in Python for the matching cluster+node (lines 288–302).
  **Inefficiency worth flagging:** it filters cluster/node in Python rather than in SQL, so
  it can load many rows just to return one. Fine at test scale, would not scale.
- **`read_config_by_id` (314–332)** / **`read_config_by_name` (335–353)** — load one config
  blob and `Config.model_validate(...)` it back into a `Config` object. The by-name one
  returns the *first* match (line 348 `.first()`), so duplicate names are ambiguous.
- **`read_all_configs` (356–367)** — returns every `ConfigRecord` in creation order; backs
  the `/get_configs` endpoint we saw in `routes.py`. Note it returns raw `ConfigRecord`
  rows, not parsed `Config` objects (the route serializes them with `model_dump`).

---

## Recap and next jump

- `init_database()` (from `app.py`) ensures the DB and both tables exist; idempotent.
- `save_config()` (from `run_test`) writes the run's config blob into `configs`, the first
  persisted row of a run.
- `save_model_log` / `save_terminal_debug` are the sinks every log in `logger.py` funnels
  into, all landing in the single `app_logs` table keyed by `config_id` + `log_type`.
- The read functions reconstruct typed models/configs back out, and `read_model_logs` is the
  one the global scheduler leans on for latency data.

That completes the two support calls in `run_test` (lines 88–89). The next line, 103, is the
big one, the call that actually drives the test:

**Next jump:** `src/strato_api/services/workload/run_workload.py` — `run_workload(...)`,
where the workload is generated and the questions are driven against the global API.
