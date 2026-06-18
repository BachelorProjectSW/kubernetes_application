# Frontend (`src/frontend/`) — what it does, file by file

React 19 + Vite + React Router + recharts. Two screens: a **Config page** (build a test
config and start a run) and a **Dashboard** (visualize and compare results). It talks to the
**Strato API** only (`VITE_CONFIG_API_URL`), never the global/cluster APIs.

Honest framing up front: the **config form is crude** (one giant flat state object, inline
styles, no client validation, a couple of real bugs), but the **dashboard is genuinely
capable** (two-run comparison, a custom node-status timeline, the latency-decomposition
chart). So it's uneven, not uniformly bad.

```
main.tsx ──► App.jsx ──► ConfigPage  ──► AllConfigs (play_around) ──► 10 input components
                      │                                    └─ handleSubmit (submitData) ─► POST /start_test
                      └► DashboardPage ─► GET /test_results, recharts
```

---

## Infrastructure

### `main.tsx` (9 lines)
Standard React 19 entry: mounts `<App/>` into `#root` inside `<React.StrictMode>`. The only
TypeScript file in the project; everything else is `.jsx` (so TS is essentially unused despite
`@types/*` being installed).

### `App.jsx` (165 lines) — routing + test lifecycle UI
- `BrowserRouter` with two routes: `/` → `ConfigPage`, `/dashboard` → `DashboardPage`, plus a
  top nav.
- **`ConfigPage` owns the run lifecycle UX.** It polls `GET /test_status` every **1.5s** while
  a test is `running`/`stopping`, shows a **lock overlay** over the form during a run (so you
  can't edit config mid-test), and **auto-redirects to the dashboard** when a test it has seen
  running goes back to `idle` (`navigate(/dashboard?config_id=...)`). This is the cleanest,
  most thoughtful part of the config side, it mirrors the backend's `idle→running→stopping`
  lifecycle in the UI.

### `services/api.jsx` (3 lines) — **DEAD / BROKEN**
```js
import fastapi from FastAPI;
```
This is **not valid JavaScript** (it's pseudo-Python). It's never imported anywhere (the
actual API call lives in `submitData.jsx`). Pure leftover cruft that should be deleted. Good
"the codebase has rough edges" example, but harmless because nothing references it.

---

## The config form

### `components/play_around.jsx` (`AllConfigs`, 105 lines) — the master form
- Holds the **entire form state** in one flat object `inputs` via `useState({})`, with a single
  `handleChange` that does `{...values, [name]: value}`. It passes `inputs` + `handleChange`
  down to every sub-component (**state lifted to one place**). On submit, calls
  `onSubmit(e, inputs)` → `handleSubmit`.
- Simple and works, but it's **one big untyped bag of keys**. There's no schema, so a typo'd
  key name silently does nothing, which is exactly how the `port_strato` bug below happens.

### `components/submitData.jsx` (`handleSubmit`, 106 lines) — flat form → Config JSON
- Transforms the flat `inputs` into the **nested `Config`** the backend expects: sums
  days/hours/minutes into `duration_time_s`, formats the date into `dd/mm/yyyy HH:MM:SS` (the
  exact format `time_utils.compute_simulated_now` parses), assembles weights/power/latency/
  workload/question/clusters/global/strato, and `POST`s to `/start_test`. Feedback via
  `alert()`.
- **Real bug (line 76):** `strato: { ip: inputs.ip_strato, port: inputs.port_global }` — the
  strato **port** reads from the *global* port field. Copy-paste error; strato's port is taken
  from the wrong input.
- **Confused dead code:** every sub-object is written `start: {...} || ""`. An object literal is
  always truthy, so `|| ""` **never** fires, it's meaningless boilerplate repeated ~6 times.
- Leftover `console.log(exportData)` twice.

### The 10 input components
All follow the **same controlled-input pattern** (`value={inputs.x}` + `onChange=handleChange`),
each collecting one slice of the config:

| Component | Collects |
|---|---|
| `experimentID.jsx` (`Ids`) | experiment name **+ "Load Existing"** (see below) |
| `startTime.jsx` | sim start date, duration (days/hours/minutes) |
| `weights.jsx` | gco2 / cost / latency sliders (0–1, default 0.5) |
| `power_schedular.jsx` | `timeout_s`, idle-turn-off seconds |
| `latency.jsx` | latency window, max latency (SLO) |
| `workloadbalance.jsx` | requests/min, pattern (steady/peaks), seed, peakiness |
| `question.jsx` | question text, max output tokens |
| `cluster.jsx` (`ClusterMangening`) | dynamic list of clusters (see below) |
| `global_schedular.jsx` | global API ip/port |
| `strato_config.jsx` | strato ip/port |

Two of these are more than trivial:

- **`experimentID.jsx` (`Ids`, 204 lines)** — besides the name field, it has a **"Load
  Existing"** mode: fetches `GET /get_configs`, and when you pick a saved run it **re-hydrates
  the entire form** from `config_json` (the reverse of `submitData`: splits the date back
  apart, converts seconds back to days/hours/minutes, fills every field). This is genuinely
  useful (reproduce/tweak a past run) and the most complex config component.
- **`cluster.jsx` (`ClusterMangening`, 164 lines)** — add/remove clusters dynamically, each with
  name/ip/port, a **dynamic GPIO-pin sub-list** (add/remove pins), and country code.
  - **Gap:** there's **no `k3d` control rendered** here. `addCluster` sets `k3d: undefined` but
    no checkbox ever sets it, so a manually-added cluster's `k3d` stays undefined (only set if
    loaded from an existing config). For local k3d testing you'd have to load an existing
    config or edit JSON.
  - Uses `key={index}` for list items (a React anti-pattern that can misrender on remove/reorder)
    and the component name is typo'd (`ClusterMangening`).

- **`weights.jsx`** — three independent sliders. **The UI does not constrain them to sum to 1**,
  even though the scoring model assumes normalized weights. No normalization, no validation; you
  can submit `gco2=1, cost=1, latency=1`. (The backend uses them as-is in the weighted sum, so
  un-normalized weights silently change the score scale.)

---

## The dashboard

### `pages/DashboardPage.jsx` (891 lines) — results visualization
The substantial half of the frontend. It loads aggregated results and renders charts.

**Data loading:**
- Reads `?config_id=` from the URL and auto-loads (this is how `ConfigPage`'s redirect lands
  you on the right run). Also a dropdown of all experiments (`GET /get_configs`).
- `fetchOneConfig(id)` → `GET /test_results?config_id=…` → the aggregated payload (built by
  `strato_api/services/test_results.py`, which we haven't documented yet).
- **Comparison mode:** you can load a *second* run and overlay it. `mergeByIndex` aligns the two
  runs **by request position** (index), not timestamp, reasonable given the fixed-seed workload
  makes runs directly comparable request-for-request.

**Charts (recharts):**
1. **Latency over time** (or primary-vs-compare latency).
2. **Cumulative gCO₂ over time** — your headline emissions metric.
3. **Cumulative cost over time.**
4. **Cluster distribution pie** — where requests were routed (shows the scheduler's choices).
5. **Service-timeout breakdown** (`ServiceTimeoutChart`) — plots `global_choose_cluster`,
   `cluster_queue_time_ms`, and `llama_inference_ms` over time. **This is the latency
   decomposition** (selection vs queue vs inference) straight from the `RequestLog` timing
   fields, directly relevant to your power-scheduler latency discussion.
6. **Worker-node status timeline** (`NodeTimelineRows` / `WorkerNodeStatusComparison`) — a
   custom, CSS-positioned timeline showing each node's IDLE/WORKING/OFF state as colored blocks
   across the run. **This visualizes the power scheduler actually turning nodes on and off**,
   the clearest visual evidence your power component works. Non-trivial code (it merges
   consecutive same-status events and positions blocks by time fraction).

**Metric cards (`MetricsGrid`):** total requests, success rate, failed, avg latency, total
gCO₂, total cost, avg renewable %.

**Small presentational components:** `Box`, `ChartCard`, `LatencyTooltip`, `ClusterDistributionChart`.

**Dashboard rough edges:**
- Imports `"./App.css"` from `pages/` (likely a wrong relative path; works only by bundler
  luck or the file isn't really there). Minor.
- Lots of inline recharts config duplicated across the three line charts (could be one
  parametric component).
- `alert(String(err))` for error handling.

---

## What the frontend does, in one paragraph

The frontend is a thin operator console for the Strato API: a config page that builds the
`Config` object and starts a run (then locks itself and polls status until the run finishes,
redirecting you to results), and a dashboard that pulls aggregated results for one or two runs
and renders latency / emissions / cost / cluster-distribution / node-timeline / latency-
breakdown charts. It's a research tool UI, functional and reasonably informative, not a polished
product.

---

## Frontend issues (for the assessment)

| Severity | Issue | File |
|---|---|---|
| Bug | `strato.port` reads `inputs.port_global` (wrong field) | `submitData.jsx:76` |
| Dead/broken | `import fastapi from FastAPI;` — invalid, unused | `services/api.jsx` |
| Gap | no `k3d` control when adding a cluster in the UI | `cluster.jsx` |
| Gap | weights not normalized / not validated to sum to 1 | `weights.jsx` |
| Misleading | "All fields will be validated before submission" — there's **no** client validation | `play_around.jsx` |
| Smell | `{...} || ""` on object literals (no-op), repeated | `submitData.jsx` |
| Smell | one giant untyped flat state object; key typos silently no-op | `play_around.jsx` |
| Smell | `key={index}` in dynamic lists; typo `ClusterMangening` | `cluster.jsx` |
| Smell | inline styles vs CSS classes mixed; `console.log`/`alert` left in | several |
| Gap | `.tsx` present but TypeScript essentially unused | all `.jsx` |
| Gap | **no frontend tests at all** | — |

**What's genuinely good:** the run-lifecycle UX (poll → lock → auto-redirect), the
load-existing-config rehydration, and especially the dashboard's **comparison mode**,
**node-status timeline**, and **latency-decomposition chart**, those three make the dashboard a
real analysis tool, not a toy. If asked about the frontend, lead with those.
