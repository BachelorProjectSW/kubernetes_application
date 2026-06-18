# `src/global_api/util/market_data_store.py` — the hourly market-data cache

`cluster_data.get_cluster_runtime_data` calls `market_data_store.get_power/get_carbon/
get_price`. This file is the **cache in front of the external data sources**. Without it,
*every request* would re-hit the Electricity Maps API (and the CSV / DK proxy) for the same
hour, slow, rate-limited, and wasteful. With it, the first request in a simulated hour
fetches; the rest reuse.

The pattern is identical for all three metrics: **key on (zone, hour) → return cache hit, or
fetch-and-store on miss.**

---

## Cache key helper and entry types (9–34)
```python
9   def _hour_floor(dt): return dt.replace(minute=0, second=0, microsecond=0)
22  @dataclass class _CarbonCacheEntry: data: list[tuple[datetime, int]]
27  @dataclass class _PriceCacheEntry:  data: list[tuple[datetime, float]]
32  @dataclass class _PowerCacheEntry:  data: list[tuple[datetime, float]]
```
- **`_hour_floor`** — rounds a timestamp down to the top of its hour. This is what makes the
  cache hour-granular: any time within `14:00–14:59` maps to the same key `14:00`. The data
  sources are hourly, so caching per hour is exactly right.
- The three `@dataclass` entries are thin typed wrappers around the cached lists (a list of
  `(timestamp, value)` tuples). They exist mostly for type clarity.

## The store and singleton (37–50, 188)
```python
48      self._carbon: dict[(str, datetime), _CarbonCacheEntry] = {}
49      self._price:  dict[(str, datetime), _PriceCacheEntry]  = {}
50      self._power:  dict[(str, float, datetime), _PowerCacheEntry] = {}
188 market_data_store = MarketDataStore()
```
- Three dictionaries, one per metric. Keys:
  - carbon/price: `(zone, hour)`.
  - power: `(zone, pv_capacity_w, hour)` — note capacity is part of the power key, because PV
    watts depend on the installed capacity, so two clusters with different capacities in the
    same zone/hour cache separately.
- Line 188 is the shared singleton imported everywhere. **In-memory, process-global** — same
  single-process assumption as the rest of the global API.

## `reset()` (52–64)
```python
62      self._carbon.clear(); self._price.clear(); self._power.clear()
```
- Empties all caches. The docstring says the important bit: **call this when a new test
  starts** so a new run doesn't reuse the previous run's cached hours. (We'll see whether the
  global `start_test` actually calls it, that's a thing to verify when we document
  `start_test.py`; if it doesn't, stale cache across runs would be a real bug. Flag to
  check.)

## `get_carbon` (66–98) / `get_price` (100–131) — same shape
```python
90      key = (zone.upper(), _hour_floor(start))
92      entry = self._carbon.get(key)
93      if entry is not None:
94          return entry.data           # cache hit
96      data = fetch_carbon_intensity(start, end, zone)   # miss → external fetch
97      self._carbon[key] = _CarbonCacheEntry(data=data)
98      return data
```
- Textbook read-through cache: build the `(zone, hour)` key, return the cached series on a
  hit, otherwise call the real fetcher (`fetch_carbon_intensity` / `fetch_price_data` in
  `price_and_carbon_intensity.py`), store, and return. `get_price` is line-for-line the same
  with the price fetcher.
- **No expiry/invalidation:** entries live until `reset()`. That's fine because simulated
  hours are immutable historical data, the carbon intensity for "July 3rd 13:00" never
  changes, so caching it forever within a run is correct.
- **Not thread-safe (worth flagging):** unlike `ConfigStore`, there's no lock here. Two
  threads missing the same key concurrently could both fetch and both write, the last write
  wins. Harmless (same data, just a duplicated fetch), but it's an unguarded shared dict that
  the per-request threads and the power-scheduler thread all touch. A "is this thread-safe?"
  question has the honest answer: *the writes are idempotent so a race only wastes a fetch.*

## `get_power` (133–185) — the DK fork
```python
165     zone_key = zone.upper()
166     key = (zone_key, float(pv_capacity_w), _hour_floor(start))
168     entry = self._power.get(key)
169     if entry is not None: return entry.data
172     if zone_key.startswith("DK"):
173         dk_hourly = get_dk_hourly(start, end)        # real measured generation
174         data = [(parse(r["timestamp"]), float(r["avg_generation_w"])) for r in dk_hourly]
181     else:
182         data = get_power(start, end, zone, pv_capacity_w)   # CSV capacity-factor estimate
184     self._power[key] = _PowerCacheEntry(data=data)
```
- Same cache logic, but the **miss path forks on zone** (172): 
  - **DK** → fetch **real measured generation** from the AAU Orin proxy via `get_dk_hourly`
    (the actual CROM microgrid). It reads `avg_generation_w` and parses the timestamp.
  - **everyone else** → estimate from the **static CSV capacity-factor table** via
    `pv_power.get_power` (capacity × hourly factor).
- This is the cache-layer realization of the **simulated-vs-real** split: Denmark is a real
  microgrid (measured PV), the rest are simulated from historical capacity factors. Same fork
  appears in `cluster_data.get_microgrid_base_load_w` for the *consumption* side.

---

## The cache in one line
> First request for a (zone, hour) pulls from the external source (Electricity Maps for
> carbon/price, CSV or DK-proxy for PV); every later request in that simulated hour is served
> from memory until `reset()`.

## Defense-worthy points
- **Hour-granular caching** matches the hourly data sources; correct and cheap.
- **PV cache key includes capacity**; carbon/price keys don't (they don't depend on it).
- **`reset()` exists for run isolation** — confirm it's actually called on test start (open
  item for `start_test.py`).
- **No locking** on the caches; safe only because re-fetches are idempotent.

## Jumps from here (the actual data sources)
| Call | File |
|------|------|
| `fetch_carbon_intensity`, `fetch_price_data` | `services/price_and_carbon_intensity.py` |
| `get_power` (CSV) | `services/pv_power.py` |
| `get_dk_hourly` (DK proxy) | `services/dk_energy.py` |
