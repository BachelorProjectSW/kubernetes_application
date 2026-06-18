# `src/global_api/services/dk_energy.py` — the real Danish microgrid (CROM)

This is the **real-microgrid** data source. While every other cluster's PV is simulated from
a CSV, the Denmark cluster reads **actual measured** generation and consumption from the AAU
Orin proxy (a service in front of the CROM microgrid's CrateDB). Two places call it:
- `market_data_store.get_power` (DK fork) → uses `avg_generation_w` as real PV output.
- `cluster_data.get_microgrid_base_load_w` (DK) → uses `avg_consumption_w` as base load.

So `get_dk_hourly` returns **both** the production and consumption side of the real microgrid.

---

## Setup (1–14)
```python
14  ORIN_BASE_URL = "http://100.74.156.93:5050"
```
- The proxy lives at a **Tailscale IP** (`100.74.x.x`), matching the report's "CROM real
  Danish microgrid via Tailscale." This is reachable only on the project's private network,
  so DK data only works when connected to Tailscale. (If unreachable, the request fails and
  propagates, no silent fallback to the CSV here, the fork happens upstream in the cache.)

## `_ms_to_iso(ms)` (17–27)
```python
27      return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```
- Converts epoch **milliseconds** (the proxy's timestamp unit) to a readable UTC string. The
  `/1000` is ms→seconds for `fromtimestamp`. Used to normalize each reading's timestamp.

## `get_dk_hourly(start, end)` (30–71)
```python
48      start_ms = int(start.timestamp() * 1000)
49      end_ms = int(end.timestamp() * 1000)
53      response = requests.get(f"{ORIN_BASE_URL}/energy/hourly", params={"start": start_ms, "end": end_ms}, timeout=60)
58      response.raise_for_status()
66      data = response.json()
67      for reading in data:
68          reading["timestamp"] = _ms_to_iso(reading["timestamp_ms"])
69          del reading["timestamp_ms"]
71      return data
```
- **Lines 48–49** — convert the datetime window to **epoch milliseconds** (the proxy's
  expected query unit). Note the round-trip: callers pass datetimes, this converts to ms for
  the API, and `_ms_to_iso` converts the response back to strings.
- **Lines 53–58** — `GET /energy/hourly?start&end` against the proxy, 60s timeout.
- **Error handling (59–64):** `HTTPError` logged with status and re-raised; connection errors
  logged with the base URL and re-raised. Same fail-loud-propagate behavior as the Electricity
  Maps fetchers, nothing swallowed.
- **Lines 66–70** — for each reading, replace the raw `timestamp_ms` field with the
  human-readable `timestamp` string (mutating the dict in place, then deleting the ms key).
- **Returns** a list of dicts, each with `timestamp`, `consumption_w`, `generation_w`. The
  two consumers each pick the field they need:
  - PV path → `avg_generation_w` (note: the consumer in `market_data_store` reads
    `avg_generation_w`, and `cluster_data` reads `avg_consumption_w`; the proxy returns the
    `avg_*` keys, the docstring's `consumption_w`/`generation_w` naming is slightly
    out-of-date vs the actual keys used by callers — a minor doc drift worth noting).

---

## Why this file matters
- It's the **one real-world data source** in the system, everything else for non-DK clusters
  is simulated/historical. This is what lets you claim the framework was validated against an
  actual operating microgrid, not only synthetic data.
- It supplies **both sides** of the DK energy picture: real PV generation (renewable output)
  and real consumption (base load), which is why DK clusters have a non-zero base load while
  simulated ones don't.

## Defense-worthy points
- **Real microgrid over Tailscale** (CROM via the Orin/CrateDB proxy); DK data requires
  network access to that proxy.
- **Supplies generation *and* consumption** — feeds both `renewable_output_w` (PV) and the
  base load.
- **Doc-vs-code key drift:** the docstring says `consumption_w`/`generation_w`, but callers
  read `avg_consumption_w`/`avg_generation_w`. The code is the source of truth; the docstring
  trails it. Good "is everything up to date?" example for your read-through.
