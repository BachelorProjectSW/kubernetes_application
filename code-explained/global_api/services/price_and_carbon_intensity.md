# `src/global_api/services/price_and_carbon_intensity.py` — Electricity Maps API

This is the **carbon intensity and electricity price** source. The cache's `get_carbon` /
`get_price` miss-paths call the two functions here, which hit the **Electricity Maps** v4 API
over HTTP. This is the live external dependency behind your carbon and cost metrics.

---

## Setup (1–27)
```python
9   load_dotenv()
11  BASE_URL = "https://api.electricitymaps.com/v4"
14  def _get_headers() -> dict:
24      api_key = os.getenv("ELECTRICITY_MAPS_API_KEY")
25      if not api_key:
26          raise RuntimeError("ELECTRICITY_MAPS_API_KEY is not set.")
27      return {"auth-token": api_key}
```
- **Line 9** — `load_dotenv()` loads a local `.env` so `ELECTRICITY_MAPS_API_KEY` is
  available in dev. (In Docker/prod the var is set in the environment directly.)
- **Line 11** — the API base. v4 endpoints used below: `/price-day-ahead/past-range` and
  `/carbon-intensity/past-range`.
- **Lines 14–27** — `_get_headers` reads the API key and returns the `auth-token` header,
  **raising if the key is missing**. So a misconfigured key fails loudly at fetch time (which,
  via the cache and `cluster_data`'s try/except, surfaces as a failed request). This is the
  one piece of required external credentials in the scoring path.

## `fetch_price_data(start, end, zone)` (30–71)
```python
48      response = requests.get(
49          f"{BASE_URL}/price-day-ahead/past-range",
51          params={"zone": zone,
53                  "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
54                  "end":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
55                  "temporalGranularity": "hourly"},
57          timeout=120)
59      response.raise_for_status()
68      entries = response.json().get("data", [])
71      return [(datetime.fromisoformat(e["datetime"]), e["value"]) for e in entries]
```
- Fetches **hourly day-ahead** prices for the zone and window. `past-range` is the historical
  endpoint (the simulated time is in the past relative to real now, so we query history).
- **Error handling (60–66):** an `HTTPError` is logged with the status code and re-raised; any
  other error is logged and re-raised. Nothing is swallowed here, failures propagate up to the
  cache/`cluster_data` (which then degrades to `0.0`). So a price outage makes a cluster look
  free, the fail-soft behavior noted in `cluster_data.md`.
- **Line 71 — units:** returns `(timestamp, value)` where **value is EUR/MWh** (per the
  docstring). This is exactly why `cluster_data` divides by 1000 to get EUR/kWh. The unit
  boundary lives here.
- **"day-ahead" caveat:** day-ahead is the wholesale market price set the day before. It's a
  reasonable proxy for "grid electricity price," but it's not a retail/consumer price, worth
  knowing if asked what the cost metric actually represents.

## `fetch_carbon_intensity(start, end, zone)` (74–116)
```python
92      response = requests.get(f"{BASE_URL}/carbon-intensity/past-range", ... "temporalGranularity": "hourly", ...)
113     entries = response.json().get("data", [])
116     return [(datetime.fromisoformat(e["datetime"]), e["carbonIntensity"]) for e in entries]
```
- Structurally identical to the price fetch (same params, same error handling), against the
  carbon endpoint. Returns `(timestamp, carbonIntensity)` in **gCO2eq/kWh**.
- **The "direct" choice (your report):** Electricity Maps offers two carbon measures,
  *direct* (only generation emissions) and *lifecycle* (includes plant construction, fuel
  supply chain, etc.). You use **direct emission factors** because only generation emissions
  are relevant to a real-time scheduling decision. The endpoint/zone returns direct intensity;
  this is the number your `carbon_ref_max = 670` normalizes against.

---

## In short
> carbon and price come **live from Electricity Maps** (`past-range`, hourly), keyed by zone
> and simulated time. Price is EUR/**MWh** here (converted to /kWh downstream); carbon is
> gCO2eq/kWh (direct factors). Missing/failed fetches propagate up and degrade to 0.

## Defense-worthy points
- **External live dependency** (needs `ELECTRICITY_MAPS_API_KEY`); the cache shields it from
  per-request load, but a run still needs network + a valid key for carbon/cost to be real.
- **Direct (not lifecycle) carbon intensity** — a deliberate modelling choice you should be
  able to justify (scheduling cares about marginal generation emissions now).
- **Day-ahead wholesale price**, not retail — what "cost" means in your scores.
- **Price unit is EUR/MWh here**, converted to EUR/kWh in `cluster_data` (`/1000`).
