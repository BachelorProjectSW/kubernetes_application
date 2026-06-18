# `src/strato_api/services/workload/generator.py` — the workload shape

`execute_workload` called `generate_workload(...)` to get the list of timestamps it fires
requests at. This file is **pure computation**: in, the workload settings; out, a sorted
list of request times (offsets in seconds from the start). No I/O, no other services, no
further jumps. It's a **leaf** of our trace.

This is the code behind your report's **workload generator** section: the request count
`N = duration · rpm/60`, the `steady` vs `peaks` patterns, the sine-superposition intensity
curve, and the fixed seed for reproducibility.

The whole thing is one function, two branches (`steady` and `peaks`).

---

## Imports (1–2)
```python
1   import random
2   import math
```
- **`random`** — for the seed, the small timing jitter, and (in `peaks`) the weighted
  sampling.
- **`math`** — for `math.pi` and `math.sin` in the peak waves.

No other imports: this confirms it's self-contained.

---

## Signature and setup (5–37)

```python
5   def generate_workload(duration_s, rpm, pattern="steady", seed=42, peakiness=0.5):
28      random.seed(seed)
30      if rpm <= 0 or duration_s <= 0:
31          return []
33      total_requests = int(duration_s * rpm / 60)
34      if total_requests <= 0:
35          return []
37      timestamps = []
```
- **Line 5** — the parameters map exactly to `WorkloadConfig`: `duration_s`, `rpm`
  (requests per minute), `pattern`, `seed`, `peakiness`. Defaults shown are the fallback
  values.
- **Line 28 — the reproducibility line.** `random.seed(seed)` fixes the random number
  generator's starting point. Every random draw after this (jitter, wave parameters,
  sampling) is now **deterministic**: the same `seed` produces the exact same schedule every
  run. This is what makes two test runs comparable, identical workload, only the scheduling
  strategy differs. It's the single most important line in the file for your experiment's
  validity. **(Caveat: `random.seed` sets the *global* RNG, so if anything else in the same
  process drew from `random` between seeding and use, determinism could be disturbed. In
  practice only this function draws here.)**
- **Lines 30–31** — guard against nonsense input (non-positive rate or duration) → empty
  schedule. Matches `run_workload`'s tolerance for an empty list.
- **Line 33 — the request count.** `total_requests = int(duration_s * rpm / 60)`. This is
  the report's **N = duration · rpm/60**: rpm is per *minute*, duration is in *seconds*, so
  dividing by 60 converts. `int(...)` truncates toward zero (floors for positives). Example:
  120s at 30 rpm → `int(120 * 30 / 60)` = `int(60)` = 60 requests.
- **Lines 34–35** — if rounding produced zero requests (very low rpm over a short window),
  return empty.
- **Line 37** — the accumulator that both branches fill.

---

## Branch 1: `steady` (39–42)

```python
39  if pattern == "steady":
40      interval = 60 / rpm
41      for i in range(total_requests):
42          timestamps.append(i * interval + random.uniform(0, 1))
```
- **Line 40** — `interval = 60 / rpm` is the **average gap between requests in seconds**
  (e.g. 30 rpm → one every 2s).
- **Lines 41–42** — place request `i` at `i * interval` (evenly spaced) **plus** a random
  `0..1s` jitter. The jitter matters: without it, all requests land on exact tick marks,
  which is unrealistically regular and can create artificial synchronization. Adding up to a
  second of noise makes the steady stream look more like real traffic while keeping the same
  average rate.
- Note: the jitter can make a later request's *base* time and an earlier one's *jittered*
  time overlap slightly, which is why the whole list is sorted at the end (line 80).

That's the entire steady pattern: evenly spaced, lightly jittered.

---

## Branch 2: `peaks` (44–78)

This builds **bursty** traffic by summing several sine waves into an "intensity" curve, then
sampling request times in proportion to that intensity. It's the report's superposition
model `I(t) = 1 + Σ aᵢ · sin(fᵢ·t + pᵢ)`.

### Choosing how many waves (48–49)
```python
48      waves = []
49      num_waves = 3 + int(peakiness * 3)
```
- Number of overlapping sine waves: **3 to 6**, scaling with `peakiness` (at `peakiness=0`
  → 3 waves; at `1.0` → 6). More waves = more complex, less predictable bursts. This is the
  "Σ" in the formula, how many terms are summed.

### Each wave's parameters (51–57)
```python
51      for _ in range(num_waves):
52          wave_length = random.uniform(duration_s * 0.1, duration_s * 0.8)
53          frequency = 2 * math.pi / wave_length
54          phase = random.uniform(0, 2 * math.pi)
55          amplitude = random.uniform(0.2, 1.0) * peakiness
57          waves.append((frequency, phase, amplitude))
```
For each wave, three random properties (all drawn from the seeded RNG, so reproducible):
- **`wave_length`** (52) — the period of this wave, between 10% and 80% of the total
  duration. So waves range from "several bumps across the run" (short period) to "one slow
  swell" (long period). Mixing periods is what produces irregular-looking bursts rather than
  a single clean oscillation.
- **`frequency`** (53) — `2π / wave_length`, the standard conversion from period to angular
  frequency so `sin` completes one cycle per `wave_length`. This is `fᵢ` in the formula.
- **`phase`** (54) — a random horizontal shift `0..2π`, so the waves don't all start at the
  same point. This is `pᵢ`. Phase offsets are what let peaks land at different times instead
  of all stacking at t=0.
- **`amplitude`** (55) — `random.uniform(0.2, 1.0) * peakiness`, how tall this wave's
  contribution is, scaled by `peakiness`. This is `aᵢ`. Higher `peakiness` → taller waves →
  sharper contrast between busy and quiet periods.

### Building the intensity curve (59–66)
```python
60      for t in range(duration_s):
61          value = 1.0  # baseline
63          for freq, phase, amp in waves:
64              value += amp * math.sin(t * freq + phase)
66          intensity.append(max(value, 0.1))
```
- For **each second** `t` of the run, compute the intensity:
  - **Line 61** — start at baseline `1.0`. The baseline is the "1 +" in the formula; it
    guarantees a steady underlying traffic level so even the quiet troughs aren't fully dead.
  - **Lines 63–64** — add each wave's contribution `amp · sin(t·freq + phase)`. Summed
    across waves, this is exactly `Σ aᵢ·sin(fᵢ·t + pᵢ)`. The overlapping sines constructively
    and destructively interfere, producing an irregular up-and-down curve.
  - **Line 66** — clamp to a floor of `0.1`. Because the summed sines can push `value`
    negative (and a negative weight is meaningless for sampling), this guarantees every
    second keeps a small positive probability of receiving a request. So no second is ever
    *impossible*, just unlikely during a trough.
- `intensity` is now a list of `duration_s` positive numbers: the relative "how busy is this
  second" weight for every second.

### Allocating requests by weighted sampling (68–78)
```python
70      second_choices = random.choices(
71          population=range(duration_s),
72          weights=intensity,
73          k=total_requests,
74      )
76      for sec in second_choices:
77          ts = sec + random.uniform(0, 1)
78          timestamps.append(ts)
```
- **Lines 70–74 — the key idea.** `random.choices` draws `total_requests` seconds **with
  replacement**, where each second's chance of being picked is proportional to its
  `intensity` weight. So busy seconds (high intensity) get picked often → many requests pile
  there → a burst; quiet seconds rarely get picked. This is how the smooth intensity *curve*
  becomes a concrete *set of request times*.
- **Why sampling instead of "requests = intensity × scale"?** The comment (68–69) explains:
  weighted sampling **preserves the exact `total_requests` count** regardless of the curve's
  shape or the rpm. A direct proportional approach would drift the total. So peaks and steady
  with the same config fire the *same number* of requests, only their *distribution in time*
  differs, again, keeping runs comparable.
- **Lines 76–78** — each chosen second gets `+ random.uniform(0, 1)` jitter so requests
  within the same second spread across it rather than all firing at the exact second
  boundary. Same jitter trick as steady.

---

## Finish (80–81)
```python
80      timestamps.sort()
81      return timestamps
```
- **Line 80** — sort ascending. Both branches can produce out-of-order times (jitter in
  steady; random sampling in peaks), and `execute_workload`'s scheduler assumes timestamps
  arrive in order (it sleeps `ts - elapsed`; out-of-order would mean negative delays and
  immediate fires). Sorting guarantees a clean monotonic schedule.
- **Line 81** — return the schedule. Back in `execute_workload`, this becomes `timestamps`,
  and one async task is created per entry.

---

## How the two patterns differ, at a glance

```
steady:  • • • • • • • • • • • •      evenly spaced + small jitter, constant rate
peaks:   •      •••••        •  ••••   same total count, clustered into bursts
                ↑ busy second (high intensity)  ↑ trough (low intensity, floor 0.1)
```
Both emit exactly `total_requests = duration_s · rpm / 60` requests; only the *timing
distribution* changes.

## Ties to the report
- **`total_requests = int(duration_s * rpm / 60)`** → report's `N = duration · rpm/60`.
- **intensity curve** `value = 1.0 + Σ amp·sin(t·freq + phase)` → report's
  `I(t) = 1 + Σ aᵢ·sin(fᵢt + pᵢ)`.
- **`random.seed(seed)`** → the fixed-seed reproducibility the report relies on for
  comparable runs.

## Possible-stale / defense notes
- `random.seed(seed)` seeds the **global** RNG, fine here, but a fragile pattern in general
  (any other global `random` use could perturb it). A dedicated `random.Random(seed)`
  instance would be more robust. Worth mentioning if asked.
- `num_waves = 3 + int(peakiness * 3)` means `peakiness` controls **both** wave count (here)
  **and** wave amplitude (line 55). So `peakiness` is overloaded, it intensifies bursts two
  ways at once. Not wrong, just good to know what the one knob actually does.
- Truncation `int(...)` on line 33 means very low `rpm` can floor to zero requests; the
  guard on 34–35 handles it.

---

## Recap and next jump

`generate_workload` is a pure, seeded function that turns the workload config into a sorted
list of request timestamps, evenly spread (`steady`) or clustered into sine-driven bursts
(`peaks`), always preserving the exact request count. It makes **no further calls**, so the
trace returns to `execute_workload`, which fires those requests at the global API.

That exhausts the Strato side of the path. The **next real jump is the cross-service
boundary**: `execute_workload` line 121 POSTs each question to the global API's
`/handle_llm_question`. So we move into **`src/global_api/`**, starting at its entry point
`app.py` and its `/handle_llm_question` route, the global scheduler, which is where your own
components (cluster selection + power scheduler) live.

**Next jump:** `src/global_api/app.py` → the `/handle_llm_question` route.
