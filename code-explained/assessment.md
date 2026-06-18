# Whole-project assessment — the good, the bad, and what to defend

This is the project-wide version (supersedes the earlier backend-only draft). It covers the
strengths to lead with, the real weaknesses ranked, the testing defense (the most likely line
of attack), and a per-area "what to be attentive to" for the exam. Built from a full read of
`src/` and `test/`.

## 0. One-paragraph verdict

The **backend is the project's strength**: a clean three-tier separation, a well-grounded
scoring model, a working coupled power scheduler, real hardware control, and validation against
a real microgrid. The **paper is strong** too, novel reproducible-comparison angle, real
hardware/data, and genuine analytical depth (it finds and correctly explains the unexpected
"balanced ≠ midpoint" result). The **weaknesses are concentrated** in three places: (1)
**testability and test coverage** of the stateful schedulers, (2) a handful of
**code-vs-report inconsistencies** (the latency reference maximum and the latency definition),
and (3) the **frontend**, which is functional but rough. None of these undermine the
contribution; all are defensible if you name them first. **Realistic grade: 10–12, with 12 in
reach** given the paper quality (individually graded, so it hinges on your sections + Q&A + code
round).

### ★ Two report-confirmed items to walk in knowing
- **`latency_ref_max`: report/experiments used 12000; code now says 25000** — changed by commit
  c2ca99d on **May 30**, *3 days after* the May 27 paper. Frame as "we fixed the flaw our own
  discussion identified." Keep 12000 on the slide. (Full story in `models/basemodels.md`.)
- **Issue B confirmed by the paper:** eq 10 explicitly defines the latency-feedback `L_obs` as
  **end-to-end**, but the code feeds it **inference** latency. Own it as a minor, one-line-fix
  inconsistency. (Grounded in `custom_logging/util/log_reader.md`.)
- Good news on testing: the paper **already discloses** the power-scheduler test gap as future
  work, so it can't be sprung on you, just discuss it maturely (§3).

---

## 1. What's genuinely good (lead with these)

- **Clean tiered architecture.** Strato (orchestration) → global (scheduling) → cluster
  (node-level + hardware), each a thin-routes/fat-services FastAPI app sharing models and DB.
  The separation of concerns is real and consistent.
- **The scoring model is well-designed and well-tested.** Grid-fraction blending, fixed-max
  normalization (with a defensible reason over min-max), weighted sum giving a total order.
  Unit-tested at the math level.
- **The two components are genuinely coupled** — cluster selection and the power scheduler both
  read the same score, so traffic and capacity grow on the same cluster. That's an elegant
  design story, not an afterthought.
- **Idempotency-aware, no-double-counting telemetry.** Retries only on pre-arrival connection
  failures; Strato only logs a failure if the request never reached the host. Thoughtful.
- **Reproducibility is taken seriously.** Fixed-seed workload + simulated-time replay make runs
  directly comparable, the backbone of a credible experiment.
- **Real hardware + real data.** GPIO power-on through an optocoupler, SSH shutdown, and the DK
  cluster reads a real microgrid (CROM) over Tailscale. This is more than a simulation.
- **The dashboard does real analytical work** — two-run comparison, a node-status timeline that
  visualizes the power scheduler acting, and a latency-decomposition chart.

---

## 2. Biggest issues (whole project, ranked by exam relevance)

| # | Issue | Where | Defensible framing |
|---|-------|-------|--------------------|
| 1 | **Test coverage of the stateful schedulers** (power scheduler, orchestration, concurrency) is thin | see §3 | "Validated end-to-end, not in isolation; a design-for-testability gap." |
| 2 | **Latency-definition inconsistency**: throughput uses inference (correct, matches report); but `S=L_obs/L_max` is fed inference while **report eq 10 explicitly says end-to-end (twice)** | global `power_scheduler.py:310-313`; readers in `log_reader.py` | "Throughput term is consistent; the latency-feedback term uses inference where the report says end-to-end. Minor, one-line fix to align." |
| 2b | **`latency_ref_max` code≠report**: report/experiments = 12000, code = 25000 (changed May 30, post-submission) | `models/basemodels.py:181` | "We fixed the flaw our discussion identified (12000 too low); change post-dates the paper. Slide keeps 12000." |
| 3 | **Process-global state → one process per service, one test at a time** | every service | "An accepted scope decision for a research harness; not built to horizontally scale." |
| 4 | **Silent fail-soft biases results**: missing market data → `0.0` → cluster looks clean/cheap | `cluster_data.py` | "A data gap should exclude a cluster, not flatter it; we'd make it explicit." |
| 5 | **`choose_cluster` returns `None` if all clusters off → crash** | `scoring.py:201` | "Prevented by the keeper invariant, not by the function; should be guarded explicitly." |
| 6 | **Security shortcuts**: DB password `strato`, SSH `AutoAddPolicy`, user=pass=node name, `CORS *`+credentials, `shell=True`, f-string `CREATE DATABASE` | several | "All acceptable only because everything is on an isolated Tailscale network; not production-hardened." |
| 7 | **Hot-path scaling cost**: N live HTTP calls per question for scoring; Python-side log filtering | `cluster_data.py`, `postgres.py` | "Fine at test scale; scheduler overhead grows with fleet size." |
| 8 | **Frontend bugs/gaps**: `strato.port` wrong field; broken `api.jsx`; no `k3d` UI control; weights not normalized; "validated before submission" is false | frontend | "The frontend is an operator tool, not a product; these are real but low-impact." |
| 9 | **Dead/stale code**: unused `stay_one`, unused `TypeVar`, `{...}||""` no-ops, doc/key drift, prod imports a test fixture | several | "Leftovers from iteration; we can point them out, which shows we know the code." |

Items 2–9 are also your **Limitations / Future Work** material.

---

## 3. The testing defense (the most likely attack — prepare this hardest)

### 3.1 Facts (know cold)
- **~65 unit tests** across 14 files (~1,500 lines).
- **6 integration scenarios** (`test/integration/test_k3d_integration.py`), each spinning up
  **real k3d clusters** and running a full workload through all three services: default,
  high-load, and cluster-switching under **gco2 / cost / latency** weights and with **DK**.
- CI runs the full k3d stack on every change.

### 3.2 The frame: a deliberate two-layer strategy
- **Unit tests cover the deterministic decision logic** — scoring math, `choose_cluster`
  (greenest wins under carbon weight, etc.), node-selection policy, the slot model, the workload
  generator, the data/cache/time helpers. **Cluster selection, the headline contribution, is
  unit-tested.**
- **Integration tests cover emergent behaviour** — the six k3d scenarios validate the actual
  thesis claims (carbon-first routes to the greenest cluster; load triggers scaling) end-to-end.

> **Headline answer:** "We tested in two layers, unit tests for the deterministic logic and six
> end-to-end k3d scenarios for the scheduling behaviour under different weights and load, so both
> the parts and the system are validated, each at the appropriate layer."

### 3.3 Say the gap before they do
Thin spot = **component-level tests of the stateful, side-effecting modules in isolation**: the
**power scheduler's decision math**, the **orchestration** (`handle_llm_request`), the **async
workload driver**, and **concurrency** (the locks and three concurrency models are reasoned
about but not stress-tested). The per-service `test/integration/*` folders were scaffolded but
left empty.

### 3.4 Why the gap exists — the insight that makes it credible
> "Scoring is well-tested *because* it's pure functions. The power scheduler isn't, *because* it
> mixes the decision math with HTTP, hardware control, and global state, so testing it in
> isolation needs mocking we didn't build. If we'd extracted the scheduler's math into pure
> functions the way we did for scoring, it would have been unit-testable too, and we'd likely
> have caught the latency-definition inconsistency earlier. That's the main thing we'd change."

### 3.5 How we mitigated it otherwise
- End-to-end k3d integration exercises the scheduler/orchestration in the real call path.
- **The experiment results are themselves system validation** — the ~53% emission reduction and
  the latency/renewable shifts only occur if scaling and routing actually work.
- Validation against **real hardware and a real microgrid** is a form of acceptance testing.
- CI catches regressions in the integrated behaviour.

### 3.6 Likely questions → crisp answers
- **"Core contribution isn't tested?"** → "Cluster selection is unit-tested; the power
  scheduler's logic is validated via the six integration scenarios, not isolated unit tests,
  because its code entangles logic with I/O. We'd refactor to pure functions to unit-test it."
- **"Coverage %?"** → "We didn't measure it, so I won't guess. Qualitatively: deterministic
  logic well covered, stateful schedulers covered at integration not unit level. I'd run
  `pytest --cov`." **(Never invent a number.)**
- **"How do you know the power scheduler is correct?"** → "High-load and switching k3d tests
  show nodes scaling and traffic moving; and the experiment deltas depend on it working. The
  missing piece is an isolated unit test like `estimate_required_nodes(8000, 1) == 8`, trivial
  to add."
- **"Concurrency tested?"** → "No, genuine gap. The critical sections are small and standard,
  but we wrote no race/stress tests."
- **"GPIO/SSH testing?"** → "Abstract hardware behind an interface, inject a fake, assert the
  calls; keep a small hardware-in-the-loop suite. Currently those call `subprocess`/`paramiko`
  directly, so they're not unit-testable."
- **"Empty integration folders?"** → "We scaffolded per-service and consolidated on one k3d
  end-to-end suite; we'd fill or remove them."

### 3.7 One-sentence version
> "Unit tests for the deterministic logic, six end-to-end k3d scenarios for the scheduling
> behaviour; the honest gap is isolated testing of the stateful schedulers and concurrency,
> which is a consequence of mixing decision logic with I/O, and the thing we'd most change is to
> make that math pure so it's as testable as scoring."

---

## 4. What to be attentive to, per area (quick exam map)

| Area | If they push here, your move |
|---|---|
| **Cluster selection** | Strong ground. Map every slide term to a line; defend fixed-max normalization (absolute scale, the A-vs-B example). Watch the all-off → `None` edge and tie-break-by-config-order. |
| **Power scheduler** | Know `μ=1000/inference_ms`, `N=⌈λ/μ⌉`, `S=L_obs/L_max`, `max` not sum, fleet-wide estimate + scoring-order placement. **Own issue #2 (latency definition) proactively** and point at the call site. |
| **Testing** | §3. Lead with the two-layer frame, then name the gap and the design reason. |
| **Scalability** | Concede the single-process model (issue #3) as a scope decision; DI would fix it. |
| **Data validity** | The `0.0` fail-soft (issue #4); direct vs lifecycle carbon; day-ahead vs retail price; simulated time runs 1:1. |
| **Hardware** | GPIO pulse through optocoupler; SSH `sudo shutdown`; keeper + double in-flight guard. Security shortcuts are "Tailscale-isolated only." |
| **Frontend** | Lead with the dashboard's real features (comparison, node timeline, latency breakdown). Concede the form is crude and name the `port_strato` bug before they find it. |
| **Reproducibility** | Fixed seed + simulated-time replay; same config → same workload. Strong ground. |

---

## 5. What we'd do differently (consolidated)

1. **Extract scheduler decision logic into pure functions** (like scoring) → unit-testable; would
   have surfaced issue #2.
2. **Dependency injection instead of global singletons** → fixes testability *and* the
   single-process limitation (issue #3) in one move.
3. **Make data failures explicit**, not silent `0.0` (issue #4).
4. **Add concurrency/failure-path tests** and **fill the integration scaffolding**.
5. **Reconcile the report's `L_obs` definition with the code** (issue #2).
6. **Frontend:** add client validation, fix the `port_strato`/`k3d` gaps, delete dead `api.jsx`,
   normalize weights in the UI.

---

## 6. Coverage of this deep-dive (for reference)

Documented in `code-explained/`: all of Strato, the global API (incl. both scheduler halves and
all data sources), the cluster API (incl. hardware control + a Kubernetes primer), logging,
persistence, and the frontend. **Not yet documented** (minor, none defense-critical):
`global_api/services/{ensure_nodes_ready,get_all_worker_nodes,validate_config}.py`,
`strato_api/services/{test_results,workload/run_workload_display}.py`,
`custom_logging/{models/log_models,util/log_reader}.py`, `models/{basemodels,enum}.py`. Of
these, `log_reader.py` is the only one tied to a live issue (it defines inference- vs
end-to-end-latency, issue #2).
