# Likely exam questions + answers

Drill sheet. Organized by topic. Answers are crisp and grounded in the code + paper. Bold = the
line to actually say. "↳ If pushed" = the follow-up they'll probe. Your components are **cluster
selection** and the **power scheduler**, so those sections are deepest.

Companion sheets: `energy-cheatsheet.md`, `stats-and-results-defense.md`, `assessment.md`.

---

## A. Motivation & framing

**Q1. What problem does this project solve?**
> Routing LLM inference across microgrid-powered clusters in a renewable-aware way is an open
> problem. Prior work either simulates, or evaluates a *single fixed* strategy. **We built a
> framework that lets operators compare scheduling strategies side-by-side on real hardware under
> identical, reproducible workloads**, so they can pick the trade-off (carbon/cost/latency) that
> fits their priorities, or simulate a planned cluster before building it.

**Q2. Why microgrids / why does this matter?**
> Data centers were ~1.5% of global electricity (~415 TWh in 2024, projected >945 TWh by 2030,
> AI-driven). Microgrids let clusters run on locally produced renewable energy, cutting carbon and
> cost, but that needs a scheduler that decides *where* to run each request based on local
> renewable availability, grid carbon, price, and latency.

**Q3. What's novel vs related work?**
> Prior work (Andersen/Mumberg, Boelskifte) evaluated a single fixed strategy or used mismatched
> weather data across countries. **Our contribution is reproducible side-by-side comparison of
> multiple weight configurations under an identical workload and simulated-time-aligned data**, so
> differences are attributable to the strategy, not to noise or temporal mismatch.

---

## B. Cluster selection / scoring (your component)

**Q4. How does cluster selection work?**
> Once per request, each cluster gets a **score = w_c·carbon + w_e·cost + w_l·latency**, a weighted
> sum of three normalized metrics. Weights sum to 1 and are operator-set (carbon weight 1 =
> carbon-first, etc.). **Highest score wins.** Because it's a weighted sum it gives a single total
> order, so there's always exactly one best cluster.

**Q5. What is "blending" / the grid fraction?**
> Carbon and cost aren't used raw, they're scaled by the share of power drawn from the grid:
> **f_grid = max(0, 1 − P_renewable/P_load)**, and blended metric = grid metric × f_grid. The
> assumption is **locally produced renewable energy is zero-carbon and zero-cost**, so only the
> grid-supplied fraction counts. A cluster in sunshine genuinely scores cleaner and cheaper.

**Q6. Why fixed reference maxima instead of min-max normalization?** *(your strongest design point)*
> Min-max scores each metric only *relative to the clusters present*, losing absolute scale.
> Example: cluster A at 0.03 €/500 gCO₂ vs B at 0.30 €/450 gCO₂, min-max ties them at ~0.5 even
> though A is 10× cheaper for 10% more carbon. **Fixed maxima (670 gCO₂, 0.30 €, latency) preserve
> absolute scale, so A correctly wins.** `v_norm = max(0, 1 − value/ref_max)`.
> ↳ If pushed (the downside): the fixed European worst-case maxima compressed the low-carbon DK/FR
> range into a narrow band, which is *why balanced resembled latency-first*, we analyze this in the
> discussion, and making the maxima configurable is future work.

**Q7. Why is latency in the score at all?**
> Energy data is hourly, so without latency the chosen cluster would stay chosen all hour while it
> degrades and the other sits idle. **Latency lets the operator decide whether they care about
> responsiveness.** It's the average end-to-end latency over a recent window; if no requests were
> routed there, it's 0 ms (max score), so it doesn't bias a cold start.

**Q8. What latency does scoring use, end-to-end or inference?**
> **End-to-end** (the average of per-request `latency_ms` over the window). That's the right choice
> for routing, it reflects what the user experiences.

**Q9. Tie-breaking / edge cases?**
> Ties go to the **first cluster in config order** (strict `>`). A cluster with all nodes powered
> off is excluded. ↳ If *every* cluster were off, `choose_cluster` returns None, in practice
> prevented by the keeper invariant (one node always on), though not guarded in the function itself.

---

## C. Power scheduler (your component)

**Q10. What does the power scheduler do and how is it split?**
> A periodic background loop in the global API decides **how many** nodes the fleet needs; the
> **cluster API executes** (GPIO on, SSH off). Each cycle: scale up first, then turn off idle
> nodes. **At least one node per cluster always stays on (the keeper).**

**Q11. Walk me through the turn-on math.**
> Two signals, take the larger:
> - **Throughput:** μ = 1000/inference_ms (a node's req/s = reciprocal of its service time;
>   the 1000 is ms→s). **N_required = ⌈λ/μ⌉**, where λ = requests/sec. N_throughput = N_required −
>   N_active.
> - **Latency feedback:** if average latency > the limit, **S = L_obs/L_max**, N_scaled = ⌈N·S⌉,
>   N_latency = N_scaled − N_active.
> - **N_add = max(N_throughput, N_latency)** — max not sum, because both estimate the *same* total
>   from different assumptions; summing would double-count.

**Q12. Why divide 1000 by latency? Isn't ms→s a divide-by-1000?**
> μ is a **rate** = reciprocal of service time. Service time in seconds = latency_ms/1000, and
> μ = 1/(latency_ms/1000) = **1000/latency_ms** req/s. The /1000 flips to the numerator because we
> invert. Example: 8000 ms = 8 s/req → μ = 0.125 req/s; demand λ=1 → ⌈1/0.125⌉ = **8 nodes**.

**Q13. How does it choose *which cluster* gets the new nodes?** *(common confusion)*
> Not by per-cluster traffic, it never measures that. It computes the fleet-wide deficit, then
> **distributes nodes to clusters in scoring order (greenest first under carbon weights)**, filling
> each cluster's OFF nodes until the budget is spent. This works because cluster *selection* already
> routes traffic to the same high-scoring cluster, **the same scorer drives both routing and where
> capacity grows.** That's the coupling that ties my two components together.

**Q14. How does turn-off work?**
> A global guard: **if the cluster's average end-to-end latency exceeds the SLO, skip the whole
> turn-off pass** (don't shed capacity while slow). Otherwise each cluster turns off nodes that have
> been **idle past a threshold**, but never the **keeper** (lowest-named node, always on) and never
> a node with **in-flight requests** (checked twice: filtered out, then re-checked after a 10 s pause
> before the SSH shutdown).

**Q15. Where does λ (request rate) come from?**
> Counting **LogSent rows** (written by Strato at dispatch) over the latency window, divided by the
> window seconds. So demand is measured at the source. ↳ Debatable whether it should be measured at
> the global API instead; we note that in the code.

**Q16. ⚠️ What latency does the *power scheduler* use, inference or end-to-end?** *(landmine, issue B)*
> The **throughput** term correctly uses **inference** latency, matching the paper's service-time
> definition (time actively processing, excluding waiting). For the **latency-feedback `S` term**,
> the code feeds **inference** latency, but the paper (eq 10) defines `L_obs` as **end-to-end**.
> **It's a minor inconsistency, both values are computed in `log_reader.py`, a one-line change to
> align.** The turn-off SLO guard does use end-to-end, so turn-down is consistent with the paper.

**Q17. What stops it powering off a busy node?**
> Two layers, cluster-side: nodes with in-flight requests are filtered out before selection, and
> after a node is marked TURNING_OFF it sleeps 10 s and **re-checks** in-flight, aborting back to
> IDLE if a request arrived. Plus the keeper guarantees one node never turns off.

---

## D. ⚠️ The code-vs-report landmines (know these cold)

**Q18. The code says `latency_ref_max = 25000` but the report says 12000. Which is it?**
> **All experiments and the report used 12000.** The code was changed to 25000 by a commit on
> **May 30, three days after the paper (May 27).** We made that change because our own discussion
> showed 12000 was *too low*, it compressed latency normalization toward 0 under load and made
> balanced resemble latency-first, so we raised it to address exactly that, which we'd flagged as
> future work. **The slide keeps 12000 because that's what produced the reported results.**

**Q19. So the current code wouldn't reproduce your reported results?**
> Correct for the latency normalization, with 25000, a 20000 ms latency normalizes to 0.2 instead
> of ~0, which is the whole point of the fix. Reproducing the *reported* numbers needs 12000;
> the current default reflects our post-submission improvement.

**Q20. (Issue B again, if they read both)** See Q16, own it as a minor inference-vs-end-to-end wiring
inconsistency in the `S` term, one-line fix, both readers exist in `log_reader.py`.

---

## E. Energy modeling *(see energy-cheatsheet.md for depth)*

**Q21. Direct vs lifecycle carbon, why direct?**
> Direct emission factors, only generation emissions, because a real-time scheduling decision cares
> about the marginal emissions of generating power *now*, not embodied lifecycle emissions. Lifecycle
> is a valid alternative the framework could swap in.

**Q22. Where does PV come from?**
> Capacity factor (0–1, weather-derived from the Copernicus Pan-European Climate Database) ×
> **fixed 1500 W** installed capacity. DK uses **real measured generation** from the CROM microgrid.

**Q23. Is the energy realistic? `power_scale_factor`?**
> The hardware (Jetson Nano) draws a few watts (idle 1.19 W, active 6.10 W); we **scale by 50** to
> model data-center-scale magnitudes. So **absolute energy figures are comparative, not literal
> hardware measurements**, the paper says this explicitly. Relative comparisons between strategies
> are what matter.

**Q24. Price, retail or wholesale?**
> **Day-ahead wholesale** (EUR/MWh → /kWh) from Electricity Maps. Not retail, so absolute cost is
> understated but the time-of-day pattern is right.

---

## F. Architecture, Kubernetes, hardware

**Q25. Describe the architecture.**
> Three tiers: **Strato** (Ubuntu server, runs the frontend, workload generator, DB), **global
> scheduler** (Raspberry Pi 5, does cluster selection + power scheduling), and **one cluster API per
> cluster** (Pi 5 control plane) that selects a worker node and forwards to a **llama-server pod on a
> Jetson Nano**. All on a Tailscale VPN, all telemetry to PostgreSQL.

**Q26. How is Kubernetes used? Does K8s schedule the LLM?**
> **No, K8s gives us the inventory; our code does the scheduling.** llama-server runs as a
> DaemonSet (one pod per worker). We use the K8s API only to *discover* nodes (IP, Ready state) and
> the llama pod's port. Our own `choose_worker_node` picks the node. We also use K8s for power-pod
> lifecycle (delete → DaemonSet recreates).

**Q27. How do you physically power nodes on/off?**
> **On:** the Pi pulses a **GPIO pin through an optocoupler** wired to the Jetson's power button (a
> 0.5 s high-low = a button press), electrically isolated. **Off:** **SSH `sudo shutdown`** for a
> graceful OS/K8s shutdown.

**Q28. How does node selection within a cluster work?**
> Slot-aware: prefer a fully **idle** node (by name, deterministic), else the node with most **free
> slots** (`max_slots − active`), else round-robin if all full. **Idle-first concentrates load on
> purpose so other nodes stay idle and can be powered off**, routing and energy-saving are coupled.

---

## G. Testing *(see assessment.md §3)*

**Q29. How did you test this?**
> Two layers: **~65 unit tests** for the deterministic logic (scoring math, selection policy, slot
> model, workload generator, data/cache helpers) and **6 end-to-end k3d integration scenarios** that
> run full workloads through all three services and validate the actual scheduling behaviour
> (carbon-first routes to the greenest cluster, etc.).

**Q30. Is the power scheduler tested?**
> Cluster *selection* is unit-tested. The power scheduler's decision logic was **validated through
> the integration scenarios and manual testing, not isolated unit tests**, which the paper discloses
> as future work. The reason is design: scoring is pure functions so it's trivially testable; the
> scheduler mixes the math with HTTP, hardware, and global state. **If we'd extracted the math into
> pure functions like scoring, it'd be unit-testable, that's the main thing we'd change**, and it
> would've surfaced the latency inconsistency earlier.

**Q31. Coverage percentage?**
> We didn't measure it, so I won't guess. Qualitatively: deterministic logic well covered, stateful
> schedulers covered at integration not unit level. I'd run `pytest --cov` to quantify.

---

## H. Statistics & results *(see stats-and-results-defense.md)*

**Q32. Did you do statistical significance testing?**
> No, we reported descriptive comparisons. For the latency results a **non-parametric test like
> Mann-Whitney U** would be appropriate, latency is heavily right-skewed with timeout outliers, so it
> violates the normality assumption a z-test/t-test needs. Future work, along with more independent
> runs per config, since two repeats isn't enough for run-level statistics and per-request samples
> within a run aren't independent.

**Q33. What were the headline results?**
> Carbon-first vs latency-first: **emissions cut ~53% (98.21 → 46.22 gCO₂), renewable share 26.1% →
> 49.7%, average latency rose 9436 → 11227 ms.** Balanced (equal weights) **did not land in the
> middle, it resembled latency-first** because the fixed reference maxima compressed the low-carbon
> carbon/cost range, so latency dominated the score.

**Q34. Why didn't balanced land in the middle? (key analytical question)**
> The fixed maxima are European worst-case (670 gCO₂, 0.30 €), but DK and France both have low-carbon
> grids, so their blended carbon/cost values sit in a **narrow band at the top of the normalized
> range** (carbon term varied only ~0.03). Latency varied across the **full** range. So under equal
> weights, **latency dominated** and balanced looked like latency-first. Calibrating the maxima to
> observed ranges (future work) would fix this.

---

## I. Limitations & "what would you do differently"

**Q35. Biggest limitations?**
> Only 2 clusters / 2 countries, 8 rpm, single global-scheduler instance (scalability not
> established, per-request DB reads grow with rate); PV is hourly historical with no within-hour
> variation; battery storage not modeled; energy figures are scaled/comparative not literal; fixed
> reference maxima. All in the paper's limitations section.

**Q36. What would you do differently?**
> (1) Extract the scheduler's decision math into **pure functions** so it's unit-testable (and it'd
> have caught the latency inconsistency). (2) **Dependency injection** instead of global singletons,
> fixes testability *and* the single-process limitation. (3) Make data failures explicit instead of
> silently degrading to 0. (4) More runs + non-parametric significance tests. (5) Make the reference
> maxima configurable.

**Q37. Does it scale?**
> Honestly, not as-is. Each service holds **process-global state (one process, one test at a time)**,
> and scoring makes N live HTTP calls per request plus a per-request DB read for latency. Fine at our
> scale; for production you'd want DI, a shared state store, and the global scheduler itself running
> on K8s (future work).

---

## J. Reproducibility & methodology

**Q38. How are runs reproducible / comparable?**
> **Fixed-seed workload** (same seed → same request schedule) replayed in **simulated time** (a
> chosen historical moment, e.g. 25/03/2026 03:00, so PV/carbon/price are identical across runs).
> Only the weights change between the main experiments, so differences are attributable to the
> strategy.

**Q39. What is simulated time and does it run faster than real time?**
> It maps wall-clock to a chosen simulated moment: `simulated_now = simulated_start + (now −
> real_start)`. It runs **1:1 with real time**, just offset, so a 6-hour test covers 6 simulated
> hours. (This is also why the dashboard's time axis shows real time, a constant offset, cosmetic.)

**Q40. Three concurrency models, why?**
> **Threads** to get the workload off the HTTP request thread (so /start_test returns fast).
> **Asyncio** in the workload driver to keep hundreds of I/O-bound requests in flight on one thread.
> **ThreadPool** to power on multiple nodes in parallel (each boot takes seconds). Each fits its job:
> threads for background work, asyncio for fan-out waiting, threadpool for parallel slow I/O.

---

## K. Fast-recall facts (memorize)

- Score: `w_c·carbon + w_e·cost + w_l·latency`, weights sum to 1, highest wins.
- Grid fraction: `f_grid = max(0, 1 − P_renewable/P_load)`; blended = grid × f_grid.
- Normalization: `max(0, 1 − value/ref_max)`; maxima **670 gCO₂, 0.30 €, 12000 ms** (report).
- Throughput: `μ = 1000/inference_ms`, `N_required = ⌈λ/μ⌉`. Latency: `S = L_obs/L_max`. `N_add = max(...)`.
- Hardware: Pi 5 control planes, Jetson Nano workers, GPIO+optocoupler on, SSH shutdown off, Qwen2.5-1.5B on llama.cpp.
- Data: Copernicus PV ×1500 W, Electricity Maps (direct carbon + day-ahead price), CROM real DK microgrid.
- Results: **−53% CO₂ (98.21→46.22)**, renewable 26.1%→49.7%, latency 9436→11227 ms, balanced ≈ latency-first.
- Experiment: 6 h, 2880 req, 8 rpm, peaks, seed 23, DK + France, SLO max_ms 10000, window 180 s.
- Landmines: `latency_ref_max` 12000 (report) vs 25000 (code, post-submission fix); `S` term fed inference vs report's end-to-end.
