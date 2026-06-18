# `src/global_api/util/time_utils.py` — simulated time

`handle_llm_request` called `compute_simulated_now(...)` to figure out "what simulated moment
is it right now." This tiny file is the whole simulated-clock mechanism, and it's central to
your experiment design, so it's worth knowing cold.

The idea (from CLAUDE.md and your report): a test runs *now*, but it replays a *simulated*
moment (say a sunny July noon) so PV / carbon / price are looked up for that simulated time.
The simulated clock advances at the same rate as the real clock; it just starts from a
different point.

```python
4   SIMULATED_TIME_FORMAT = "%d/%m/%Y %H:%M:%S"
27      now_utc = datetime.now(timezone.utc)
29      simulated_start = datetime.strptime(start_time_simulated.strip(), SIMULATED_TIME_FORMAT).replace(tzinfo=timezone.utc)
32      real_start = datetime.fromisoformat(start_time_real.replace("Z", "+00:00"))
33      if real_start.tzinfo is None:
34          real_start = real_start.replace(tzinfo=timezone.utc)
35      else:
36          real_start = real_start.astimezone(timezone.utc)
38      elapsed = now_utc - real_start
39      return simulated_start + elapsed
```

- **Line 4** — the simulated start is given in `dd/mm/yyyy HH:MM:SS` (European day-first
  format). That's the format the frontend/config provides.
- **Line 27** — read the real wall-clock now, in UTC.
- **Line 29** — parse the configured **simulated** start string into a datetime and stamp it
  UTC. `.strip()` tolerates stray whitespace.
- **Lines 32–36** — parse the **real** start timestamp. It's ISO format; the `replace("Z",
  "+00:00")` handles the `Z` suffix Python's `fromisoformat` historically didn't accept.
  Lines 33–36 make sure the result is timezone-aware UTC whether or not the input carried a
  zone. (Defensive parsing, two formats for two fields: simulated start is the custom
  day-first format, real start is ISO.)
- **Line 38 — the core.** `elapsed = now − real_start`: how long the test has actually been
  running.
- **Line 39 — the formula:** `simulated_now = simulated_start + elapsed`. The simulated clock
  is just the simulated start plus however long we've really been running. **It runs at 1:1
  real speed** (no time compression/dilation), one real second is one simulated second; only
  the *offset* differs.

## Why it matters for your defense
- This is the single function behind "simulated time." Every energy lookup in `cluster_data`
  uses its output, so the carbon/price/PV all correspond to the simulated moment, not now.
- **1:1 rate** is the key property: a 10-minute test covers 10 simulated minutes. If someone
  asks "could you simulate a whole day in a short run," the honest answer is *not with this
  function* — it would need a time-scale multiplier, which isn't here.
- It's a **pure function** (no I/O, no state), so it's deterministic given its two inputs.
  No further jumps.
