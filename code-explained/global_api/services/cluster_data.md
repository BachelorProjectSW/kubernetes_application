# `src/global_api/services/cluster_data.py` — sourcing the scoring inputs

`handle_llm_request` calls `get_cluster_runtime_data(...)` once per cluster (line 68) to
build the `ClusterRuntimeData` that `choose_cluster` then scores. So **this file is where the
raw numbers come from**: renewable output, grid carbon, grid price, and current cluster load.
It's the bridge between the energy data sources and your scoring component.

It makes calls outward to three places:
- **`market_data_store`** — cached PV / carbon / price lookups (the Pan-European Climate
  Database + Electricity Maps data).
- **the cluster API** (`GET /get_cluster_working_nodes`) — to count how many nodes are
  active/idle right now (for the load calculation).
- **`dk_energy`** — a Denmark-specific base-load addition (the real CROM microgrid path).

---

## Imports and module state (1–16)
```python
7   from .dk_energy import get_dk_hourly
8   from .scoring import compute_cluster_load
9   from ...custom_logging.models.log_models import MarketSnapshotLog
10  from ...db.postgres import save_model_log
11  from ..util.all_configuration import config_store
12  from ..util.market_data_store import market_data_store
16  _logged_market_hours: set[tuple[str, str, datetime]] = set()
```
- **`compute_cluster_load`** (8) — note this is imported from **`scoring.py`** (the function
  we just documented). Load is defined once there and reused here; no duplicate formula.
- **`market_data_store`** (12) — the in-memory cache that serves PV/carbon/price; avoids
  re-hitting the external APIs for every request. **Jump candidate:** `util/market_data_store.py`.
- **`get_dk_hourly`** (7) — Denmark base-load lookup. **Jump candidate:** `dk_energy.py`.
- **Line 16 — a module-global `set`** used to remember which (config, cluster, hour) market
  snapshots have already been logged, so each simulated hour is logged once. This is
  **in-memory dedup state**: same single-process caveat as everything else, and it persists
  across requests for the life of the process (not cleared between runs unless the process
  restarts, a subtle point, see below).

---

## `_log_market_snapshot_if_new(...)` (19–51) — log each hour once
```python
33      config = config_store.get()
34      if config is None or config.id is None:
35          return
37      key = (config.id, cluster_name, simulated_hour)
38      if key in _logged_market_hours:
39          return
41      _logged_market_hours.add(key)
42      save_model_log(config.id, MarketSnapshotLog(... carbon..., cost...))
```
- Persists the hourly carbon + price for a cluster as a `MarketSnapshotLog`, but **only the
  first time** that (config, cluster, simulated-hour) combination is seen (the `set`
  membership check on 38). Without this dedup, every request in the same simulated hour would
  write an identical market row, thousands of duplicates.
- **Why it matters for results:** this is how the report can plot "carbon/price over the
  simulated day", one clean row per cluster per hour.
- **Stale-state note for the defense:** `_logged_market_hours` is **keyed by `config.id`**,
  so a new run (new id) won't collide with an old one, good. But the set is never emptied, so
  a very long-lived process slowly accumulates keys. Harmless at test scale; worth noting as a
  minor unbounded-growth smell.

---

## `get_microgrid_base_load_w(...)` (54–81) — Denmark's always-on draw
```python
74      country_code = cluster.simulated_country_code.upper()
76      match country_code:
77          case code if code.startswith("DK"):
78              dk_hourly = get_dk_hourly(simulated_time_start, simulated_time_end)
79              return float(dk_hourly[0]["avg_consumption_w"])
80          case _:
81              return 0.0
```
- Adds a **fixed background load** (the comment example: a fridge, i.e. real household/site
  loads on the actual Danish microgrid) for DK-backed clusters, and **0 for everywhere else**.
- This is the seam between the **simulated** clusters (PV from a database, no base load) and
  the **real CROM microgrid** in Denmark, which has genuine non-compute consumption that must
  be accounted for in the load. Uses `get_dk_hourly` to read that real consumption for the
  hour. **Jump candidate:** `dk_energy.py`.
- The `match/case` with a guard (`case code if code.startswith("DK")`) is just "if the
  country code starts with DK." Only Denmark has a real microgrid behind it; the rest are
  pure simulation.

---

## `get_cluster_runtime_data(...)` (84–193) — the main builder

Called per cluster from `handle_llm_request`. Wrapped in one big `try/except` (108–193) that
**logs and re-raises** on failure (so a broken cluster surfaces rather than silently
returning bad data).

### Energy-market lookups (109–124)
```python
109     simulated_time_end = simulated_time_start + timedelta(hours=1)
111     pv = market_data_store.get_power(simulated_time_start, simulated_time_end, cluster.simulated_country_code, energy.pv_capacity_w)
114     renewable_output_w = pv[0][1] if pv else 0.0
116     carbon_data = market_data_store.get_carbon(simulated_time_start, simulated_time_end, cluster.simulated_country_code)
119     grid_carbon_intensity = float(carbon_data[0][1]) if carbon_data else 0.0
121     price_data = market_data_store.get_price(simulated_time_start, simulated_time_end, cluster.simulated_country_code)
124     grid_electricity_price = (price_data[0][1] / 1000) if price_data else 0.0
```
- **Line 109** — defines a **one-hour window** starting at the simulated time. All three
  lookups are hourly (the data sources are hourly resolution).
- **Lines 111–114 — PV / renewable output.** Looks up the solar capacity factor for this
  country at this simulated hour and scales by `energy.pv_capacity_w` (the fixed 1500 W
  capacity from your report). `pv[0][1]` is the value of the first (and only) hourly row;
  `if pv else 0.0` guards an empty result. This is `P_renewable` for the grid fraction.
- **Lines 116–119 — grid carbon intensity** (gCO2/kWh) for the hour. This is the raw grid
  metric that scoring later *blends*.
- **Lines 121–124 — grid electricity price.** Note the **`/ 1000`**: the source gives price
  per MWh, divided by 1000 to get per kWh (the unit your `cost_ref_max = 0.30 EUR/kWh`
  expects). A unit-conversion to be aware of, the stored price is EUR/kWh.
- Each lookup degrades to `0.0` if the store returns nothing, so a missing data point makes a
  cluster look maximally clean/cheap rather than crashing. (Subtle scoring implication: a
  data gap *flatters* a cluster. Worth knowing.)

### Log the hourly snapshot (126–132)
- Rounds the simulated time down to the hour (126) and calls `_log_market_snapshot_if_new`
  (127–132) so this hour's carbon/price is recorded once.

### Count active vs idle nodes (134–153)
```python
134     url = f"http://{cluster.ip}:{cluster.port}/get_cluster_working_nodes"
135     response = requests.get(url, timeout=180)
146     for node_data in worker_nodes_payload:
147         worker_node = WorkerNode.model_validate(node_data)
148         if worker_node.status == WorkerStatus.WORKING:
149             active_nodes += 1
150         elif worker_node.status == WorkerStatus.IDLE:
151             idle_nodes += 1
153     cluster_load_w = compute_cluster_load(active_nodes, idle_nodes, energy)
```
- **Line 134–137 — a live call to the cluster API** to get its current node list. So building
  runtime data is **not** purely local; it queries each cluster's `/get_cluster_working_nodes`
  every scoring pass. (This is a per-request, per-cluster HTTP call, a cost worth being aware
  of: N clusters → N HTTP gets per question, on top of the forward.)
- **Lines 146–151** — tally nodes by status: `WORKING` → active, `IDLE` → idle. Nodes in
  other states (turning on/off, offline) count as **neither**, so they don't contribute load.
- **Line 153** — feed the counts into `compute_cluster_load` (from `scoring.py`) → the
  cluster's `P_load` in scaled watts.

### Add base load, assemble result (163–189)
```python
163     microgrid_base_load_w = get_microgrid_base_load_w(cluster, simulated_time_start, simulated_time_end)
168     cluster_load_w += microgrid_base_load_w
179     all_nodes_powered_off = active_nodes == 0 and idle_nodes == 0
181     return ClusterRuntimeData(
182         renewable_output_w=renewable_output_w,
183         cluster_load_w=cluster_load_w,
184         grid_carbon_intensity=grid_carbon_intensity,
185         grid_electricity_price=grid_electricity_price,
186         avg_latency_ms=avg_latency_ms,
187         all_nodes_powered_off=all_nodes_powered_off)
```
- **Lines 163–168** — add the Denmark base load (0 for everyone else) to the compute load.
- **Line 179 — `all_nodes_powered_off`**: true only if there are *no* active and *no* idle
  nodes. This is the exact flag `choose_cluster` checks (168–170) to exclude a cluster. Note
  it's based on the WORKING/IDLE counts, a cluster whose only nodes are mid-transition would
  read as "powered off" here.
- **Lines 181–189 — the assembled `ClusterRuntimeData`**: renewable output, total load,
  grid carbon, grid price, the avg latency (passed straight through from
  `handle_llm_request`), and the powered-off flag. **This is precisely the bundle
  `choose_cluster`/`score_cluster` consume**, every field maps to a scoring input.

### Failure handling (191–193)
- On any exception, warn and **re-raise**. So a failed runtime-data build propagates up to
  `handle_llm_request` (where it lands in the outer `except` and becomes a 500). Deliberate:
  scoring on stale/garbage data would be worse than failing the request.

---

## The data-flow picture

```
get_cluster_runtime_data(cluster, simulated_time, energy, avg_latency)
  ├ market_data_store.get_power  → renewable_output_w   (P_renewable)   [PV DB]
  ├ market_data_store.get_carbon → grid_carbon_intensity                [Electricity Maps]
  ├ market_data_store.get_price  → grid_electricity_price (/1000 → /kWh) [Electricity Maps]
  ├ GET cluster /get_cluster_working_nodes → active/idle counts
  │     └ compute_cluster_load(active, idle, energy) → cluster_load_w   (P_load)  [scoring.py]
  ├ get_microgrid_base_load_w (DK only) → += base load                  [dk_energy.py]
  └ ClusterRuntimeData{...}  ──────────────────────────────────────────► choose_cluster (scoring.py)
```

## Function calls from this file (jump list)
| Call | Defined in | Status |
|------|-----------|--------|
| `market_data_store.get_power/get_carbon/get_price` | `util/market_data_store.py` | jump candidate |
| `compute_cluster_load(...)` | `scoring.py` | done |
| `requests.get(.../get_cluster_working_nodes)` | **cluster_api** | cross-service |
| `get_microgrid_base_load_w` → `get_dk_hourly` | `dk_energy.py` | jump candidate |
| `_log_market_snapshot_if_new` → `save_model_log` | this file / `postgres.py` | done |
| `config_store.get()` | `util/all_configuration.py` | jump candidate |

## Defense-worthy points
- **Building runtime data hits each cluster's API live** (one `GET /get_cluster_working_nodes`
  per cluster per question). Scoring is not a purely local calculation.
- **Price is converted MWh→kWh via `/1000`** (line 124), the unit that matches `cost_ref_max`.
- **Missing market data degrades to `0.0`**, which makes a cluster look clean/cheap, a
  fail-soft choice with a scoring side effect worth acknowledging.
- **PV uses a fixed `pv_capacity_w`** (1500 W) × the hourly capacity factor, your report's PV
  model.
- **DK clusters carry a real base load** (`get_microgrid_base_load_w`); simulated clusters
  don't. This is the simulated-vs-real-microgrid seam.

**Remaining input-side jumps before the request leaves the global tier:**
`util/all_configuration.py` (`config_store`), `util/time_utils.py` (`compute_simulated_now`),
`util/market_data_store.py` (the cache), and `dk_energy.py` / `pv_power.py` /
`price_and_carbon_intensity.py` (the actual data sources). After those, the trace forwards to
the **cluster API** (`handle_llm_request.py:111`), the third tier.
