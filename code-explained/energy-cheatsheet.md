# Energy cheat-sheet — drill this before the exam

For the energy-background examiner. The goal is **not** energy-engineering depth, it's to say
confidently *what each number means, where it comes from, and how it enters the scheduling
decision*. Each item: the one-liner, the **why**, and the likely follow-up. Drill the bold bits.

> Golden rule: when pushed on physics, **pivot to the algorithm** ("here's how that number
> enters the score"), that's your turf. If you don't know an energy detail, **say so and reason
> from what the code does**. Never bluff an energy expert.

---

## The 7 core concepts

### 1. Carbon intensity
- **gCO₂/kWh of the grid**, fetched from **Electricity Maps** (`/carbon-intensity/past-range`,
  hourly).
- **You use *direct* emission factors, not lifecycle.** Direct = only emissions from generating
  the electricity. Lifecycle would add plant construction, fuel supply chain, etc.
- **Why direct:** a real-time scheduling decision cares about the **marginal emissions of
  generating power right now**, not embodied lifecycle emissions. *(If they prefer lifecycle:
  concede it's a defensible alternative, the framework could use either; you chose the one
  that reflects the operational decision.)*

### 2. Electricity price
- **Day-ahead wholesale price**, from Electricity Maps (`/price-day-ahead`), in **EUR/MWh**,
  converted to **EUR/kWh** (÷1000) in `cluster_data.py`.
- **Why day-ahead:** it's the hourly market price set the day before, a reasonable proxy for
  "what grid energy costs this hour." **Caveat to volunteer:** it's *wholesale*, not retail/
  consumer price, so it understates absolute cost but tracks the right *time-of-day pattern*.

### 3. PV / solar (the renewable supply)
- **Capacity factor × installed capacity.** Capacity factor is a **0–1 fraction** = how much of
  the panel's nameplate rating is actually produced that hour (0 at night, ~peak at sunny
  midday). It's **weather-derived** (reanalysis data), so it's realistic, not a clean sine.
- Installed capacity is a **fixed 1500 W** per cluster (`pv_capacity_w`).
- **Source split:** simulated clusters read capacity factors from a bundled CSV
  (Pan-European Climate Database); **DK reads *real measured* generation** from the CROM
  microgrid. Capacity is config; the factor is data.

### 4. Grid-fraction blending (the heart of the energy model)
- **`f_grid = max(0, 1 − P_renewable / P_load)`** — the share of the cluster's power that must
  come from the grid after local solar is used.
- **Blended metric = grid metric × f_grid.** So `blended_carbon = grid_carbon × f_grid`, same
  for cost.
- **Why:** **locally produced renewable energy is treated as zero-carbon and zero-cost**, so only
  the grid-supplied share carries emissions/price. A cluster in sunshine genuinely scores
  cleaner and cheaper because more of its load is covered locally.
- *Example:* solar covers half the load → `f_grid = 0.5` → the cluster sees half the grid's
  carbon and half its price.

### 5. `power_scale_factor` (Pi-watts → realistic scale)
- `cluster_load = (active·active_w + idle·idle_w) × power_scale_factor`.
- **Why:** the real hardware is Raspberry-Pi/Jetson-class drawing only a few watts; the scale
  factor multiplies measured watts up to model a **realistic data-center-scale cluster**, so the
  energy numbers are representative rather than tiny.
- Be honest: it's a **modelling multiplier**, your absolute watts are scaled, not literal Pi
  consumption. The *relative* comparisons between clusters are what matter.

### 6. Microgrid
- A **local generation + local load behind one grid connection point** (here: solar + the
  cluster's own draw, plus, for DK, real site consumption like a fridge).
- **DK is a *real* microgrid** (CROM, read live over Tailscale, both generation and
  consumption); **all other clusters are simulated** from historical data.
- This is what lets you claim validation against an **actual operating microgrid**, not only
  synthetic data.

### 7. Normalization reference maxima
- `v_norm = max(0, 1 − value / ref_max)`; fixed maxima: **carbon 670 gCO₂/kWh, cost 0.30
  EUR/kWh, latency 12000 ms**.
- **Why fixed (not min-max):** fixed European worst-case references preserve **absolute scale**,
  so a genuinely low-carbon country (DK/FR) still scores well in absolute terms instead of only
  relative to its rivals.
- **Caveat to volunteer:** these are hand-picked worst-case values, and they **compressed the
  low-carbon clusters into a narrow band**, which is why the *balanced* strategy in the results
  leaned toward latency-first rather than landing in the middle. (Owning this preempts the
  obvious attack.)

---

## How it all becomes a decision (the pivot target)

```
per cluster:  f_grid = 1 − renewable/load
              blended_carbon = grid_carbon × f_grid     blended_cost = grid_price × f_grid
              norm(x) = max(0, 1 − x/ref_max)
score = w_carbon·norm(blended_carbon) + w_cost·norm(blended_cost) + w_latency·norm(latency)
→ highest score wins;  weights sum to 1 (operator sets the strategy)
```
When energy talk gets uncomfortable, walk them down this, it converts a physics question into an
algorithm question you fully control.

---

## Likely energy-examiner questions → crisp answers

- **"Direct vs lifecycle carbon, why?"** → Direct; scheduling cares about marginal generation
  emissions now. Lifecycle is a valid alternative the framework could swap in.
- **"Is day-ahead price the right cost signal?"** → It's the hourly wholesale market price, a
  good proxy for time-of-day cost; it's not retail, so absolute magnitude is lower but the
  pattern is right.
- **"Where does the 1500 W / 670 / 0.30 / 12000 come from?"** → Installed PV capacity assumption;
  fixed worst-case European references for normalization. Hand-chosen, and we know they biased
  the balanced case, name the trade-off.
- **"How is renewable energy counted as free?"** → The grid-fraction blend: local renewable
  zeroes out its share of carbon and cost; only the grid share is charged.
- **"Is `power_scale_factor` realistic?"** → It's a deliberate multiplier to lift Pi-scale watts
  to data-center scale; relative cluster comparisons hold, absolute watts are modelled.
- **"Real or simulated energy data?"** → DK is real (CROM microgrid, measured gen + load);
  others simulated from PV capacity factors + Electricity Maps. Carbon/price are real API data
  for the simulated moment.
- **"Why does simulated time matter for energy?"** → Carbon/price/PV vary by hour-of-day and
  season; simulated time replays a chosen moment (e.g. sunny July noon) so the energy conditions
  are controlled and reproducible. Runs at 1:1 real speed.
- **"Could a cluster be charged for energy it didn't draw / double-counted?"** → No; load is
  computed from active/idle node counts × per-node watts × scale, plus DK base load; blending
  only charges the grid share.

---

## Two safety lines (memorize verbatim)

- **When unsure:** "I'd want to check the exact figure, but in our model that value enters as
  *[carbon/cost/latency]* and affects the score by *[…]*." (Pivot to the algorithm.)
- **When challenged on a modelling choice:** "That's a fair alternative; we chose *[X]* because
  *[operational reason]*, and the framework is designed so that input could be swapped without
  changing the scheduling logic." (Turns a weakness into a design strength: the scoring is
  decoupled from the data source.)
```
