# Examiner Q&A Cheat Sheet — quick-glance answers

> One or two lines each. For the full versions see `code-and-review.md` Part D.

## Scoring

**Weighted sum vs lexicographic/Pareto?**
Weighted sum is a tunable scalar (weights sum to 1) giving a total order so we can always
route one cluster. Lexicographic ignores secondary metrics; Pareto returns a set, not a pick.

**Why fixed reference maxima, not min-max?**
Min-max throws away absolute scale and creates false ties (A 10× cheaper than B still ties).
Fixed maxima keep magnitude. Values: 670 gCO2 (Ember worst-case EU), 0.30 EUR/kWh, 12000 ms.

**Why didn't equal weights give a midpoint?**
Both grids were low-carbon, so carbon/cost saturated near the top of the range (spans ~0.094
/ ~0.044) while latency spanned 0–1. Latency dominated. Fix: operator-configurable maxima.

**Renewable > load, or zero load?**
Grid fraction `1 - min(renewable/load,1)` floored at 0 → blended carbon/cost = 0 (fully
green/free). Surplus is discarded, no negative carbon, no storage carry-over.

**Isn't latency double-counted with the power scheduler?**
No. Scorer uses latency to decide *where* (placement); power scheduler uses it to decide
*how many nodes* (capacity). Different levers, they form a feedback loop, not redundancy.

**Does config order bias ties?**
Strict `>` means first-in-config wins exact ties. Rare (4-decimal floats), deterministic,
chosen on purpose for reproducible replay. Could randomize if it mattered.

**Load→grid-fraction feedback, can it oscillate?**
More nodes → higher load → lower renewable fraction → slightly worse carbon score. That's
*negative* feedback, self-limiting/stabilizing. No formal stability proof (limitation).

## Power scheduler

**Walk through one loop iteration.**
Sleep → re-read config → score+sort clusters → read rps, inference latency, active count →
compute throughput need and latency need, take max → power on best-cluster-first → then if
end-to-end latency ≤ SLO, shut down idle non-keeper nodes past the idle threshold.

**Why max of the two scale-up signals, not sum/average?**
Both estimate the same total (nodes needed) from different assumptions. Summing double-counts
and over-provisions; averaging can under-provision. Max provisions for the binding constraint.

**Derive the throughput formula. Queueing assumption?**
μ = 1000/inference_latency req/s per node; N = ⌈λ/μ⌉ so Nμ ≥ λ (M/M/c stability). Assumes
per-node service rate is constant under concurrency — which is why the latency signal exists.

**Why always keep one node on?**
Cold start is ~5 min (power-on + pod ready), and the scorer skips all-off clusters, so the
keeper (lowest-named node) guarantees baseline availability and a routable target.

**Request arrives mid-shutdown — what protects you?**
TURNING_OFF excludes the node from routing; we sleep 10s then re-check in-flight and abort to
IDLE if any arrived. Best-effort, not a cross-service transaction (limitation).

**Why GPIO pulse on, but SSH shutdown off?**
Off node has no software, so only the physical button works (GPIO pulse via optocoupler).
Running node needs a graceful OS shutdown (SSH) so K3s drains and the disk syncs cleanly.

**What prevents flapping?**
Idle-time threshold (hysteresis) + latency guard (no shutdown while slow) + keeper. No
explicit cooldown between scale-up and scale-down — a reasonable improvement.

**Node never becomes ready?**
Readiness wait polls up to 300s; on timeout the node is forced OFF with 0 slots and logged,
so it's excluded from routing rather than blocking or being falsely marked usable.

**Why turn-on inference latency but turn-off end-to-end?**
Scale-up wants pure per-node rate (queue is what you're removing); scale-down guards
user-visible end-to-end QoS. The latency-scaling term using inference time is the real
inconsistency to justify or fix.

## General / methodology

**Is 53% valid given reconstructed energy + scale factor 50?**
Yes as a *relative* claim: both runs share the same method/constants, which cancel in the
ratio. The absolute gCO2 numbers are not real-world measurements and aren't claimed as such.

**Why only 2 clusters / 8 rpm? Scaling?**
Hardware-limited; 8 rpm keeps a 6h run at 2880 requests. The single global scheduler (DB read
+ per-cluster fetch per request) is the bottleneck — future work: run it on Kubernetes.

**Why no battery model?**
Out of scope. Surplus renewable is discarded, so the system understates achievable renewable
share. Biggest realism gap; would feed a state-of-charge term into the grid fraction.

**How reproducible, given per-request DB reads + HTTP hops?**
Decisions reproduce (anchored to simulated time + historical data + fixed seed). Timing
doesn't — real inference/HTTP vary latency, shifting latency-driven ties and failures.
