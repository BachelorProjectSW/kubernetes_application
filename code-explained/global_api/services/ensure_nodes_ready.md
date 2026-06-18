# `src/global_api/services/ensure_nodes_ready.py` — wait for a cluster to be serveable

Called from the global `start_test` for each cluster (after pushing config). It **powers on all
nodes and blocks until the cluster is actually ready to take traffic**, so the workload doesn't
start hitting a cluster whose nodes are still booting.

`ensure_nodes_ready(cluster, timeout_s, poll_interval_s=5)` (9–107):

- **k3d short-circuit (27–28):** if the cluster is k3d, **return immediately**, the test harness
  doesn't use power control (pods are already up and port-forwarded). Production-only logic.
- **Step 1 (32–40):** GET `/get_cluster_information` to learn the **total** node count.
- **Step 2 (43–51):** POST `/turn_on_nodes/` with `number_of_nodes = total`, power on **all**
  nodes for the run start (even ones already on). This is the "start from full capacity, then let
  the power scheduler trim" approach.
- **Step 3 — readiness poll (53–84):** every 5 s until `timeout_s`, GET `/get_cluster_working_nodes`
  and count nodes that are **IDLE/WORKING with `max_slots > 0`**; break when **all** are ready.
  (Same two-gate readiness as the cluster side: usable status **and** real capacity.)
- **Step 4 — drain poll (86–104):** then poll `/get_cluster_information` until **total in-flight
  requests == 0**, so the cluster is fully **settled** before the workload begins. Returns when
  drained, or warns on timeout.

## Why it matters
- It's the reason a run starts against a **warm, fully-powered, settled** cluster rather than one
  mid-boot, which keeps the early latency measurements meaningful.
- It's all best-effort: every failure **logs and continues/returns** rather than raising, a
  cluster that won't come up degrades the run but doesn't crash start-up. (Trade-off: a partial
  cluster could start serving; the warnings are the only signal.)

## Defense-worthy points
- **Runs start at full capacity** (turn on all nodes), then the power scheduler scales down, this
  is the "scale from full, not from cold" choice; relevant to how your early-run node timelines
  look.
- **Two readiness gates** (status + `max_slots>0`) then a **drain gate** (no in-flight).
- **k3d skips power control entirely** — another instance of the test-vs-prod seam.
