# `src/global_api/services/pv_power.py` — PV from the capacity-factor CSV

This is the **simulated-clusters** PV source (everyone except DK). The cache's `get_power`
miss-path calls this. It reads a static CSV of hourly **capacity factors** (0.0–1.0) per
country and multiplies by the installed capacity to get watts. This is your report's PV model
for the Pan-European Climate Database data.

---

## The data file (10)
```python
10  DATA_PATH = Path(__file__).parent.parent / "data" / "pv_all_countries_2025_2026Q1.csv"
```
- Points at `src/global_api/data/pv_all_countries_2025_2026Q1.csv`, bundled in the repo. So
  PV for simulated clusters is **fully local** (no API). The filename shows the coverage:
  all countries, 2025–2026 Q1. Columns are per-country capacity factors keyed by a `Date`.
- `Path(__file__).parent.parent` = up from `services/` to `global_api/`, then into `data/`.

## `floor_to_hour` (13–15)
- Same hour-flooring as the cache, so the lookup timestamp matches the CSV's hourly `Date`
  rows exactly.

## `get_power_factor_by_time(start, end, country)` (18–45)
```python
30      if country.upper().startswith("DK"):
31          country = "DK"
33      results = []
34      start = floor_to_hour(start); end = floor_to_hour(end)
36      with DATA_PATH.open() as f:
37          reader = csv.DictReader(f)
38          for row in reader:
39              timestamp = datetime.strptime(row["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
40              if start <= timestamp <= end:
41                  results.append((timestamp, float(row[country])))
42              elif timestamp > end:
43                  break
45      return results
```
- **Lines 30–31** — normalize any `DK*` zone to the CSV column `DK`. (Even though DK's PV
  normally comes from the real proxy, this keeps the CSV path working if it's ever used for
  DK, e.g. as a fallback.)
- **Lines 36–41** — open the CSV, iterate rows, parse each `Date`, and collect
  `(timestamp, capacity_factor)` for rows **within the window**. `row[country]` selects the
  column for that country, so the CSV is wide (one column per country).
- **Lines 42–43 — a small optimization:** the CSV is time-ordered, so once a row's timestamp
  is past `end`, it `break`s instead of scanning the rest of the file. Reasonable, though it
  still re-opens and re-scans from the top on every miss (the cache is what keeps that from
  happening per request).
- **Capacity factor** is a fraction 0.0–1.0: the share of nameplate capacity actually
  produced that hour (0 at night, up toward 1 at sunny midday). It's weather-derived
  (reanalysis data), which is why it's realistic rather than a clean sine.

## `get_power(start, end, country, pv_capacity_w)` (48–72)
```python
65      factors = get_power_factor_by_time(start, end, country)
67      for timestamp, factor in factors:
68          available_power = pv_capacity_w * factor
69          results.append((timestamp, available_power))
72      return results
```
- Turns capacity factors into **watts**: `available_power = pv_capacity_w × factor`. With the
  report's `pv_capacity_w = 1500 W`, a factor of 0.4 → 600 W of solar that hour.
- Returns `(timestamp, watts)` tuples, exactly what `cluster_data` reads as
  `renewable_output_w` (it takes `pv[0][1]`, the watts of the first hourly row).

## In short
> simulated PV = (hourly capacity factor from the bundled CSV) × (installed capacity in
> watts). Local, deterministic, weather-realistic. This is `P_renewable` for non-DK clusters.

## Defense-worthy points
- **PV for simulated clusters is a local CSV**, not a live API — reproducible and offline.
- **`pv_capacity_w` is the one scaling knob** (1500 W in your runs); capacity factors are
  data, capacity is config.
- The CSV is **re-read on each cache miss** (mitigated by the hour-cache above it).
