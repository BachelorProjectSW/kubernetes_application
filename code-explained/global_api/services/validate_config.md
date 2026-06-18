# `src/global_api/services/validate_config.py` — pre-flight config validation

This is what Strato calls (`/validate_config`) **before** starting a run. It's the gatekeeper:
if it returns errors, the test never starts. It runs **five** layers of checks and concatenates
all errors. More thorough than you'd expect, worth knowing because it answers "how do you stop a
bad config?".

`validate_config(config)` (244–273) runs the pipeline and returns `{valid, errors}`:
```
validate_config_values        ← intrinsic / deterministic checks (no network)
+ validate_cluster_reachability ← can we reach each cluster API?
+ validate_electricity_maps     ← is carbon/price data available for non-DK zones?
+ validate_dk_energy            ← is the DK proxy reachable for DK zones?
+ validate_pv_data              ← is PV data available for each zone?
```

### `validate_config_values` (14–85) — the deterministic checks
Local checks, no network. Notable ones (this is your answer to "what does it validate?"):
- **unique id and name** (queries the DB; skipped gracefully if no DB, so CI/unit tests pass).
- duration > 0, request/minute > 0, and **would generate ≥ 1 request** (`duration/60 × rpm ≥ 1`).
- **★ weights must sum to 1.0** (`abs(sum − 1.0) > 0.01`) **and be non-negative.** So even though
  the **frontend doesn't constrain the weight sliders, the backend rejects weights that don't sum
  to 1** — you literally cannot start a test with bad weights. (This *softens* the frontend
  "weights not normalized" issue: it's a UX gap, not a correctness hole.)
- clusters present, **unique cluster names**, every cluster has **≥ 1 GPIO**.
- question non-empty, max_output_tokens > 0.
- latency `max_ms > 0` and `latency_window_s > 0` (both error messages say "latency must be > 0",
  a copy-paste so the window error is mislabeled, minor).
- **start time matches `dd/mm/yyyy HH:MM:SS`** exactly.

### `validate_cluster_reachability` (88–116)
GETs each cluster's `/get_cluster_information`; any failure → "cluster X unreachable". So a typo'd
IP or a down cluster is caught before the run.

### `validate_electricity_maps` (119–166)
For each **non-DK** cluster, actually calls Electricity Maps for the **simulated start→end window**
and errors if carbon or price data is missing/empty. So a run won't start if the energy data the
scoring depends on isn't actually available for the chosen simulated time. Good, fail early.

### `validate_dk_energy` (169–204)
Same idea for **DK** clusters: checks the CROM proxy returns data for the window.

### `validate_pv_data` (207–241)
Checks PV data is retrievable for every cluster's zone (uses the default `EnergyConfig().pv_capacity_w`).

## Defense-worthy points
- **The backend validates weights sum to 1** (`:51–53`) — so the frontend's lack of weight
  normalization can't actually produce an invalid run. Lead with this if asked about the weights.
- **Validation is deep:** intrinsic constraints + cluster reachability + real data-availability
  checks for the exact simulated window. A run won't start if its energy data isn't fetchable.
- Strato deliberately delegates this to the global API because the global API owns the scheduling/
  energy domain (the cross-service call we saw at `strato start_test:46`).
- Minor: duplicated "latency must be > 0" message for the window check.
