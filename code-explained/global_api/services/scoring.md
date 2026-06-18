# `src/global_api/services/scoring.py` — your Cluster Selection component

This is the literal core of your Scoring Algorithm slides. Everything here is pure
computation (no I/O, no other services), so it's a **leaf** of the trace and a file you
should be able to recite. It implements, exactly:

- **the weighted sum** `score = w_c·carbon + w_e·cost + w_l·latency` (`score_cluster`),
- **grid-fraction blending** `f_grid = max(0, 1 − P_renewable/P_load)` (`compute_grid_fraction`),
- **blended metrics** `metric × f_grid` (`compute_carbon_blend`, `compute_cost_blend`),
- **fixed-max normalization** `v_norm = max(0, 1 − value/ref_max)` (`normalize_value`),
- **the selection loop** highest-score-wins (`choose_cluster`).

The functions build on each other bottom-up: load → grid fraction → blends → normalize →
score → choose. I'll explain in that order, since that's how the math composes.

---

## `compute_cluster_load(active_nodes, idle_nodes, energy)` (8–22)

```python
20      active_power = active_nodes * energy.node_power_active_w * energy.power_scale_factor
21      idle_power = idle_nodes * energy.node_power_idle_w * energy.power_scale_factor
22      return active_power + idle_power
```
- Computes the cluster's **power draw in watts**: active nodes draw `node_power_active_w`
  each, idle nodes draw `node_power_idle_w` each, summed.
- **`power_scale_factor`** is the key modelling knob (from `EnergyConfig`, documented in
  CLAUDE.md): the real hardware is Pi-class and draws only a few watts, so to simulate a
  *realistic data-center cluster* the measured watts are scaled up by this factor. Be ready
  to explain this: your `P_load` is measured-pi-watts × scale, not literal Pi consumption.
- This is the `P_load` that feeds the grid fraction. Note it's called from `cluster_data.py`,
  not here, this function is the shared definition of "cluster load."

---

## `compute_grid_fraction(renewable_output_w, cluster_load_w)` (25–40)

```python
36      if cluster_load_w <= 0:
37          return 0.0
39      renewable_fraction = min((renewable_output_w / cluster_load_w), 1.0)
40      return 1.0 - renewable_fraction
```
- This is your blending formula `f_grid = max(0, 1 − P_renewable/P_load)`, implemented as
  `1 − min(P_renewable/P_load, 1)`.
- **Line 36–37** — guard: zero/negative load → grid fraction 0 (avoids divide-by-zero; a
  cluster drawing nothing is treated as fully clean).
- **Line 39** — `min(..., 1.0)` caps the renewable fraction at 100%: if solar output exceeds
  the load, you can't be *more* than fully renewable. This is the `max(0, ...)` of your slide
  formula expressed from the other side, capping renewable at 1 is the same as flooring grid
  at 0.
- **Line 40** — grid fraction = 1 − renewable fraction. So if solar covers half the load,
  `renewable_fraction = 0.5`, `grid_fraction = 0.5`.
- **Meaning:** only the **grid-supplied share** of power should carry carbon/cost; locally
  produced renewable energy is treated as zero-carbon, zero-cost. This function quantifies
  that share.

---

## `compute_carbon_blend` (43–58) and `compute_cost_blend` (61–76)

```python
57      grid_fraction = compute_grid_fraction(renewable_output_w, cluster_load_w)
58      return grid_carbon_intensity * grid_fraction          # carbon
75      grid_fraction = compute_grid_fraction(renewable_output_w, cluster_load_w)
76      return round(grid_electricity_price * grid_fraction, 4)  # cost
```
- Both are the same idea: **blended metric = grid metric × grid fraction.** A cluster running
  half on solar sees half the grid's carbon intensity and half its price.
- This is what makes "a cluster in sunshine genuinely scores cleaner and cheaper", the local
  renewable share zeroes out that portion of the carbon/cost.
- Minor asymmetry: cost rounds to 4 decimals (76), carbon doesn't (58). Cosmetic, but if
  someone notices the inconsistency, that's all it is.

---

## `normalize_value(value, ref_max)` (79–91)

```python
90      score = 1.0 - (value / ref_max)
91      return round(max(score, 0.0), 4)
```
- Your fixed-max normalization `v_norm = max(0, 1 − value/ref_max)`. A value of 0 → score
  1.0 (best); a value at `ref_max` → 0.0 (worst); anything beyond `ref_max` is floored at 0.
- **The `ref_max` is a fixed constant** (carbon 670 gCO2/kWh, cost 0.30 EUR/kWh, latency
  12000 ms from `EnergyConfig`), *not* the max among the current clusters. This is the
  deliberate choice over min-max normalization that you defend on the slide: fixed maxima
  preserve **absolute scale**, so a genuinely-cheap cluster scores high in absolute terms
  rather than merely relative to its rivals. The A-vs-B example on your slide is exactly this
  function's behavior.
- **Defense nuance:** there's no upper clamp at 1.0. It's unreachable here because all inputs
  are ≥ 0 (so score ≤ 1), but if a `value` were ever negative the score would exceed 1. Not a
  live bug, just worth knowing the bound is one-sided.

---

## `score_cluster(...)` (94–142) — the weighted sum

```python
122     blended_carbon = compute_carbon_blend(renewable_output_w, cluster_load_w, grid_carbon_intensity)
127     blended_cost   = compute_cost_blend(renewable_output_w, cluster_load_w, grid_electricity_price)
133     norm_carbon  = normalize_value(blended_carbon,  energy.carbon_ref_max)
134     norm_cost    = normalize_value(blended_cost,    energy.cost_ref_max)
135     norm_latency = normalize_value(estimated_latency_ms, energy.latency_ref_max)
137     return round(
138         (carbon_weight * norm_carbon)
139       + (cost_weight   * norm_cost)
140       + (latency_weight* norm_latency), 4)
```
- The full pipeline for **one** cluster: blend carbon and cost (122–131), normalize all
  three metrics against their fixed maxima (133–135), then take the **weighted sum**
  (137–141). This is `score = w_c·carbon_norm + w_e·cost_norm + w_l·latency_norm`, your
  headline equation, verbatim.
- Because weights sum to 1 and each normalized metric is in [0, 1], the **score is in
  [0, 1]** and is a single number, the "total order" point you make on the slide (there's
  always exactly one best).
- **The latency term is `estimated_latency_ms`**, which `choose_cluster` passes as
  `cluster_energy_data.avg_latency_ms`, i.e. the **end-to-end** average from the recent
  window (computed in `handle_llm_request`). So scoring's latency is end-to-end. (Contrast
  with the power scheduler's throughput term, which uses inference latency, the divergence
  you track.)
- Carbon and cost are **blended** (microgrid-aware) before normalizing; latency is **not**
  blended (latency has nothing to do with energy mix). Clean separation.

---

## `choose_cluster(...)` (145–205) — the selection loop

```python
163     best_cluster = None
164     best_cluster_energy_data = None
165     best_score = -1.0
167     for cluster, cluster_energy_data in zip(clusters, cluster_energy_data_list):
168         if cluster_energy_data.all_nodes_powered_off:
170             continue
171         cluster_score = score_cluster(... weights.gco2, weights.cost, weights.latency, cluster_energy_data.avg_latency_ms, energy)
194         if cluster_score > best_score:
195             best_score = cluster_score
196             best_cluster = cluster
197             best_cluster_energy_data = cluster_energy_data
205     return best_cluster, best_cluster_energy_data
```
- **Lines 163–165** — init the running best. `best_score = -1.0` so any real score (≥ 0)
  beats it.
- **Line 167** — `zip(clusters, cluster_energy_data_list)` walks the static config and its
  runtime data **in lockstep**; they must be in the same order (they are, both built from
  `config.clusters` in `handle_llm_request`).
- **Lines 168–170 — the eligibility filter.** A cluster with **all nodes powered off** is
  skipped entirely, you can't route work to a cluster with nothing running. This is where the
  power scheduler's decisions feed back into selection: if the scheduler turned a cluster
  fully off, it drops out of contention here.
- **Line 171** — score the cluster with the operator weights (`weights.gco2/cost/latency`)
  and its observed avg latency.
- **Lines 183–192** — log every cluster's score and inputs (great for your results analysis:
  you can reconstruct exactly why a cluster won).
- **Lines 194–197** — keep the max. **Strictly `>`**, so on a tie the **earlier** cluster in
  the list wins (first-listed cluster is favored). Worth knowing for reproducibility, ties
  break by config order.
- **Line 205** — return the winning cluster and its data, what `handle_llm_request` forwards
  the question to.

- **Edge case to flag for the defense:** if **every** cluster is powered off, the loop skips
  all of them, `best_cluster` stays `None`, and line 201's `best_cluster.name` raises
  `AttributeError`. In normal runs the keeper invariant (at least one node always on per
  cluster) prevents this, so it can't happen in practice, but the function itself has no
  explicit "no eligible cluster" guard. Good "what happens if..." answer to have ready: *it's
  protected by the keeper, not by this function.*

---

## How scoring maps to your slides / report

| Slide / report concept | Code |
|---|---|
| `score = w_c·carbon + w_e·cost + w_l·latency` | `score_cluster` 137–141 |
| `f_grid = max(0, 1 − P_renewable/P_load)` | `compute_grid_fraction` 39–40 |
| blended metric = grid metric × `f_grid` | `compute_carbon_blend` / `compute_cost_blend` |
| `v_norm = max(0, 1 − value/ref_max)`, fixed maxima | `normalize_value` 90–91 |
| highest score wins, total order | `choose_cluster` 194–197 |
| powered-off clusters excluded | `choose_cluster` 168–170 |
| latency metric = end-to-end avg over window | `estimated_latency_ms` ← `avg_latency_ms` |

## Defense-worthy points
- **Fixed reference maxima, not min-max**, the central design defense; `normalize_value` is
  where it lives, and `ref_max` being a constant (not a per-run max) is the whole argument.
- **`power_scale_factor`** scales Pi-watts to data-center scale; your `P_load` is a scaled
  figure.
- **Latency here is end-to-end**, while the power scheduler's throughput term uses inference
  latency, be precise about which is which.
- **Tie-break by config order** (`>` not `>=`) and the **all-off → None** edge case (covered
  by the keeper) are the two "gotcha" answers to have ready.

**Next file (per your request):** `cluster_data.py`, which builds the `ClusterRuntimeData`
that `choose_cluster` consumes, i.e. *where the renewable output, carbon, price, and load
numbers actually come from*.
