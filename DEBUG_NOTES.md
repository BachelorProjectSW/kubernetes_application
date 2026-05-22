# Debug Notes: Fast-Failing Requests in `newnewnewntest17`

## Summary

In the config `newnewnewntest17`, **7 out of 374 `RequestLog` entries** fail
suspiciously fast (32–899 ms) with a specific signature that suggests the
failure happens **before** cluster selection runs — yet a `LogSent` entry
exists for every one of them, which implies a cluster *was* picked. That
contradiction is the thing to chase.

There is a second, larger failure mode (148 × HTTP 500s from clusters); this
document focuses on the 7 fast-fails, which are the more puzzling case.

---

## Environment

Three relevant containers on the `ci` host:

- `kubernetes_application-backend-1` — FastAPI/uvicorn backend (`uvicorn src.strato_…`)
- `kubernetes_application-frontend-1` — frontend (nginx)
- `p6-postgres` — Postgres 16 on host port 5433

DB credentials (per setup doc): user `strato`, db `strato`, password `strato`.

Connect:

```
docker exec -it p6-postgres psql -U strato -d strato -P pager=off
```

---

## Relevant tables

### `configs`

```
id           integer  PK
config_id    varchar  (the string FK used by app_logs)
config_name  varchar  (human-readable, e.g. 'newnewnewntest17')
config_json  json
created_at   timestamp
```

### `app_logs`

```
id              integer  PK
config_id       varchar  (FK to configs.config_id)
log_type        varchar  ('LogSent' | 'MarketSnapshotLog' | 'NodeStatusLog' | 'RequestLog')
payload_json    json
terminal_debug  text     (empty for the fast-fails)
created_at      timestamp
```

---

## Log type counts for `newnewnewntest17`

```
 LogSent           |   300
 MarketSnapshotLog |     4
 NodeStatusLog     |  1367
 RequestLog        |   374
```

---

## Failure mode breakdown (RequestLog, success=false)

```
   failure_mode    | count | min_latency | max_latency
-------------------+-------+-------------+-------------
 cluster_500       |   148 |         924 |       11652
 no_cluster_chosen |     7 |          32 |         899
```

`no_cluster_chosen` is identified by `payload_json->>'cluster' = 'unknown'`.

---

## The 7 fast-fail rows

```
   id   |         created_at         | latency_ms | choose_ms
--------+----------------------------+------------+-----------
 721897 | 2026-05-21 15:51:36.794117 |         32 |
 723104 | 2026-05-21 15:57:34.53473  |         50 |
 722041 | 2026-05-21 15:51:56.975607 |         59 |
 722131 | 2026-05-21 15:53:14.421627 |         86 |
 721601 | 2026-05-21 15:51:03.121585 |        202 |
 722157 | 2026-05-21 15:53:31.710494 |        510 |
 722464 | 2026-05-21 15:54:44.081498 |        899 |
```

`choose_ms` = `payload_json->>'global_choose_cluster'` — **null on all 7**.

Sample payload:

```json
{
  "trace_id": "8f6e7c83-3a8f-431c-a4d6-79d792323b0a",
  "timestamp": "2026-05-21T15:57:34.534541Z",
  "cluster": "unknown",
  "node": "unknown",
  "success": false,
  "latency_ms": 50.0,
  "cluster_load_w": 0.0,
  "renewable_fraction": 0.0,
  "blended_carbon_gco2_per_kwh": 0.0,
  "blended_cost_eur_per_kwh": 0.0,
  "question": "What is the best programming language?",
  "answer": "unknown",
  "response_status_code": null,
  "all_content": "unknown",
  "global_choose_cluster": null,
  "global_total_time_ms": null,
  "cluster_queue_time_ms": null,
  "cluster_llama_inference_ms": null
}
```

Trace IDs of the 7 fast-fails:

```
c01e9e7b-5e69-404b-a368-246379b4f491
a7803fca-b733-4243-88ce-fe8e897aa722
c3b457fe-651f-405f-ad41-41aa63015a43
d913623b-5061-4fff-ace7-2173a6a099b2
34a5c635-6dcc-4828-a9ef-e2b023398c40
16460797-321f-4ccd-a50a-754430b45bcf
8f6e7c83-3a8f-431c-a4d6-79d792323b0a
```

---

## Key facts that constrain the hypothesis

1. **Nodes were available.** At 15:57:34 (a fast-fail moment) PT cluster had
   all three nodes (`nano1`, `nano2`, `nano3`) `working` and DK had
   `nano4/5/6` mostly `idle`. The "no eligible cluster" hypothesis is dead.
2. **`global_choose_cluster` is null on all 7.** This field is set during
   cluster selection. Null implies selection never completed.
3. **Every fast-fail has a matching `LogSent` row.** The `has_logsent`
   subquery returns `t` for all 7 trace_ids. But `LogSent` payloads contain a
   concrete `cluster` URL (e.g. `http://100.84.252.101:8020`), which means
   *something* picked a target before `LogSent` was written.
4. **Backend container logs are silent.** `docker logs
   kubernetes_application-backend-1` for the relevant window shows only
   `/test_status` polling lines — no traceback, no error, no access-log lines
   for the failing requests.
5. **`terminal_debug` is empty** for all 7 rows in `app_logs`.

The contradiction (point 3 vs point 2) is the puzzle. Either:

- `LogSent` is emitted from a code path that picks a cluster but doesn't set
  `global_choose_cluster` (e.g. a fallback / direct-dispatch path that
  bypasses the scoring code), **or**
- The RequestLog defaults (`"unknown"`, `null`) are being filled in by an
  outer exception handler that catches errors after `LogSent` was written but
  before the RequestLog fields could be populated from the real response.

---

## Useful queries

Fast-fail breakdown:

```sql
SELECT
  CASE
    WHEN payload_json->>'cluster' = 'unknown' THEN 'no_cluster_chosen'
    WHEN payload_json->>'response_status_code' = '500' THEN 'cluster_500'
    ELSE 'other'
  END AS failure_mode,
  COUNT(*),
  MIN((payload_json->>'latency_ms')::float) AS min_latency,
  MAX((payload_json->>'latency_ms')::float) AS max_latency
FROM app_logs
WHERE config_id = (SELECT config_id FROM configs WHERE config_name = 'newnewnewntest17')
  AND log_type = 'RequestLog'
  AND (payload_json->>'success')::boolean = false
GROUP BY failure_mode;
```

LogSent for a specific fast-fail trace_id (to see what cluster was picked):

```sql
SELECT payload_json
FROM app_logs
WHERE log_type = 'LogSent'
  AND payload_json->>'trace_id' = 'c01e9e7b-5e69-404b-a368-246379b4f491';
```

All log rows for a single trace_id, chronologically (timeline reconstruction):

```sql
SELECT created_at, log_type, payload_json
FROM app_logs
WHERE payload_json->>'trace_id' = 'c01e9e7b-5e69-404b-a368-246379b4f491'
ORDER BY created_at;
```

---

## What to investigate next in the code

The backend is a uvicorn FastAPI app under `src/strato_*/`. The places to
look:

1. **The request handler** for whatever endpoint serves the user question.
   Find where the response object / `RequestLog` payload is built, and
   identify the default values `"unknown"` / `0.0` / `null` — that's the
   "filling in placeholders on failure" path.
2. **The `LogSent` emitter.** Confirm whether it can fire from a path that
   doesn't set `global_choose_cluster`. Look for any code path that calls
   into the cluster URL directly without going through the scoring function.
3. **The cluster selection / scoring function** (whatever computes
   `global_choose_cluster`). Check whether there's an early-return or
   exception path that would leave `global_choose_cluster` unset but allow
   `LogSent` to still be written.
4. **Any broad `try/except` around the dispatch** that would swallow the
   real error and write the default RequestLog without setting
   `terminal_debug`. This is almost certainly hiding the root cause.

The likely fix is (a) narrow the exception handling so real errors propagate
into `terminal_debug` and stderr, and (b) make sure `LogSent` is only
emitted *after* cluster selection actually completes and
`global_choose_cluster` is set.

---

## Notes for whoever picks this up

- Don't grep backend logs by keyword (`error`, `failed`) — they're silent on
  these failures. Grep by trace_id instead.
- The two failure modes (fast-fail and cluster_500) are likely **different
  bugs**. The 500s are a real cluster-side error; the fast-fails are a
  backend logic / error-handling bug. Tackle them separately.
- Rarity (7/374 ≈ 2%) plus uneven latency distribution (32 ms up to 899 ms)
  suggests an intermittent condition, not a deterministic input bug. Possibly
  a race or a timeout-driven cancellation in the dispatch path.
