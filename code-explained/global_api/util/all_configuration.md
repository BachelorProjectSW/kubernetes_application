# `src/global_api/util/all_configuration.py` — the in-memory config store

`handle_llm_request` and `cluster_data` both call `config_store.get()` to read the active
`Config`. This file defines that store. It's the global API's answer to "where does the
current config live between requests" — in memory, in a single thread-safe singleton.

This is the global API's equivalent of Strato's module-global test state, but wrapped in a
small class with a lock instead of bare globals.

---

## The class and the singleton (6–21, 111)
```python
6   class ConfigStore:
20          self._config: Config | None = None
21          self._lock = threading.Lock()
111 config_store = ConfigStore()
```
- One `Config` slot (`_config`, starts `None`) and one `Lock`. Line 111 creates the single
  shared instance imported everywhere as `config_store`. So there is exactly **one** active
  config per global-API process, set when a test starts, read on every request.
- **Why the lock (docstring 9–11):** the **power-scheduler background thread** and the
  **request-handler threads** both touch `_config` concurrently. Without the lock a reader
  could see a half-written config during a `set`. Same concurrency story as Strato's
  `test_state_lock`, different data.

## `set` (23–35) and `get` (37–46)
```python
34      with self._lock:
35          self._config = config
45      with self._lock:
46          return self._config
```
- `set` replaces the whole config atomically under the lock (called from the global
  `start_test` when a run begins). `get` returns it under the lock (called per request). Both
  trivial, but the lock is the point: atomic swap, never a torn read.

## `get_clusters` (48–59)
- Convenience: returns `_config.clusters` (or `[]` if no config). Lock-guarded. Used where
  only the cluster list is needed.

## `get_cluster_information` (61–96) — note the locking pattern
```python
79      with self._lock:
81              return all_clusters         # (if no config)
82          clusters = list(self._config.clusters)   # snapshot under lock
84      for cluster_cfg in clusters:        # network calls OUTSIDE the lock
85          url = f"http://{cluster_cfg.ip}:{cluster_cfg.port}/get_cluster_information"
87          response = requests.get(url, timeout=180)
```
- Fetches live `ClusterInformation` from each cluster's API. **The locking detail is the
  lesson here (and a good defense point):** it copies the cluster list into a local
  *inside* the lock (line 82), then releases the lock and does the **slow network calls
  outside** it (84–94). This is the exact same pattern as Strato's `stop_test` (grab the
  value under lock, use it unlocked). Holding a lock across a 180s-timeout HTTP call would
  block the power-scheduler thread and every other request, so it deliberately doesn't.
- Not on the per-question path; used by diagnostics/other endpoints.

## `stop_power_scheduler` (98–108)
```python
105     with self._lock:
108         self._config.power_scheduler.start = False
```
- Flips `power_scheduler.start = False` on the live config. This is the **stop signal the
  power-scheduler loop polls** (it checks this flag each cycle to know when to exit). So the
  `/stop_test` path reaches into the config store and clears this flag, and the background
  loop notices and stops. We'll see the other end of this when we document `power_scheduler.py`.

---

## Why this matters
- It's the single source of truth for "what config is running" in the global API, read on
  every request without a DB hit (fast).
- It's **process-global, single-config** — one running test per global-API process, the same
  assumption as Strato.
- The `start` flag inside it is the **coupling point between `/stop_test` and the power
  scheduler loop** (covered fully when we reach `power_scheduler.py`).
