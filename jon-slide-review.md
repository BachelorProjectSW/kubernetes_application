# Jon's Slides — Review + What to Say (slides 15–25)

> Per-slide: a status (good as-is, or a suggested tweak) and an example of what to say.
> Scripts are ~30–60 seconds each and pull only from the report and the code, so they're
> safe to say out loud. Read the "Overall" notes first, they affect a few slides at once.

## Overall, before the per-slide notes

1. **Your section is solid and well-sequenced.** Concept first (16–21), then the actual
   code for the hardest part (22–24). That's a good structure for a defense.
2. **Three code slides for turn-on, zero for turn-off, is lopsided.** Slides 22–24 are a
   deep dive into the scale-*up* math, which is the densest thing in your talk. Plan to
   spend your real speaking energy on slide 22 (the concept: two signals, take the max),
   and treat 23 and 24 as "here is the actual implementation" that you walk through more
   briskly. If you're tight on time, 23 and 24 are the first place to compress.
3. **Two quick content adds would strengthen it:** put the A-vs-B example on the
   Normalization slide (19), and add a short closing slide that ties scoring and the power
   scheduler together before your live demo. Both are described below.
   - **Note on flow:** your section does not hand straight to Mads. After your closing
     slide you run a live demo (start a test on the frontend), walk the room to the
     hardware while it runs, then return and Mads resumes. So your closing slide should
     bridge into the demo, not into Mads. The scripts below reflect that.
4. **Hold the cluster-side execution detail (keeper, in-flight) as Q&A ammunition,** not
   slide content, since that lives in the cluster API (Omid's component). See the bottom.

---

## Slide 16 — The Global Scheduler

**Status:** Good. This is your roadmap slide. Make it clearly *yours* by naming the two
decisions and teasing that they're coupled (pays off in your closing slide).

**Say:**
> This is the global scheduler, and it's where my two components live. It makes two
> decisions. Cluster selection decides, for each request, which cluster should serve it.
> The power scheduler decides how many worker nodes are powered on in each cluster. They
> run off the same data, the renewable output, carbon intensity, electricity price,
> latency, and the operator's weights, and as I'll show at the end, they're actually
> coupled. Let me start with cluster selection.

---

## Slide 17 — Cluster Selection: Scoring Algorithm

**Status:** Good. Optionally add one bullet: "Weighted sum gives a total order, so we can
always pick exactly one cluster" (preempts the "why not Pareto" question). You can also
just say it.

**Say:**
> Cluster selection runs once per request. Each cluster gets a score, a weighted sum of
> three normalized metrics: blended carbon intensity, blended electricity cost, and
> latency. The highest score wins. The weights are set by the operator and sum to one, so
> carbon weight one gives a carbon-first strategy, latency weight one gives latency-first,
> and equal weights is balanced. Because it's a weighted sum, we always get a single total
> order, so there's always exactly one best cluster to route to. The next slides explain
> what "blended" and "normalized" mean.

---

## Slide 18 — Blending in the microgrid

**Status:** Good as-is.

**Say:**
> Carbon and cost aren't used raw, they're blended against the microgrid's own
> production. The grid fraction is one minus renewable output over total cluster load,
> floored at zero. So if local solar covers half the load, the grid fraction is one half,
> and we multiply the grid's carbon intensity and its price by that fraction. The
> assumption is that locally produced renewable energy carries zero direct emissions and
> zero generation cost, so only the grid-supplied share counts. That's what makes a
> cluster in sunshine genuinely score cleaner and cheaper.

---

## Slide 19 — Normalization

**Status:** Tweak recommended. Your bullet "Min-max normalization does not reflect scale"
is abstract, and it's your single strongest design justification, so make it concrete.

**Change:** add one bullet with the example (or at minimum say it):
- "A: 0.030 EUR, 500 gCO₂ vs B: 0.30 EUR, 450 gCO₂ → min-max ties them at 0.5, even though
  A is 10× cheaper. Fixed maxima → A correctly wins."

**Say:**
> The three metrics have different units, so we map them to a common scale: one minus the
> value over a fixed reference maximum, the worst realistic value, floored at zero. A
> perfect cluster scores one, a cluster at the reference maximum scores zero. The reference
> maxima are 670 grams of CO2 per kilowatt-hour, 30 euro-cents, and 12 seconds. We chose
> fixed maxima over min-max normalization on purpose. With min-max, each metric is scored
> only relative to the clusters in front of you. Imagine cluster A at three cents and 500
> grams, and cluster B at thirty cents and 450 grams. A is ten times cheaper for ten
> percent more carbon, clearly better, but min-max would score them both at one half and
> tie them. Fixed maxima keep the absolute scale, so A correctly wins. The trade-off is
> that these maxima are fixed values we picked, which Mads will come back to in the results.

---

## Slide 20 — Data Sources

**Status:** Good as-is. This is also a natural breather between scoring and the power
scheduler.

**Say:**
> These metrics need real data, from three sources. PV production for the simulated
> clusters comes from the Pan-European Climate Database, hourly solar capacity factors
> from reanalysis weather data, times a fixed 1500-watt capacity. Carbon intensity and
> electricity prices come from Electricity Maps, and we use direct emission factors,
> because only generation emissions are relevant to a scheduling decision. For our real
> Danish cluster, live generation and consumption come from the CROM microgrid over a
> Tailscale VPN. And everything is anchored to simulated time, so every cluster is scored
> against the same simulated moment and the runs stay comparable and reproducible. That's
> cluster selection. Now the second decision, the power scheduler.

---

## Slide 21 — Power Scheduler

**Status:** Good overview slide. The "at least one node" invariant here is the keeper,
which is enforced cluster-side, fine to state as an invariant at this level.

**Say:**
> The power scheduler keeps just enough nodes on to serve the load and powers the rest off
> to save energy. It runs as a periodic background loop, and each cycle it first decides
> whether to turn nodes on, then whether to turn idle nodes off. One hard invariant: at
> least one node always stays on in each cluster, so a cluster can never go fully dark and
> cluster selection always has a target. And the responsibility is split: the global
> scheduler decides how many nodes, and the cluster API actually executes the on and off.
> Let me show how it decides how many.

---

## Slide 22 — Turn on nodes (the two signals)

**Status:** Good, and this is the slide to spend time on. The caption is right: the node
count is the maximum of two estimates. Make sure the audience leaves understanding *why
max*.

**Say:**
> Scaling up uses two independent signals, and we take the larger of the two. The first,
> estimate_nodes_to_add, is a throughput model: given the current request rate and how
> fast a node serves requests, how many nodes does the load need? The second,
> apply_latency_scaling, is a safety signal based on observed latency: if we're over the
> latency limit, it asks for more nodes regardless of the throughput estimate. We take the
> max because the two estimate the same thing, total nodes needed, from different
> assumptions. Summing them would double-count and over-provision; the max provisions for
> whichever constraint is actually binding. The next two slides show the actual code
> behind each of these.

---

## Slide 23 — Turn on nodes, continued (throughput model)

**Status:** Good. This is where the latency-to-rate conversion lives. Be ready to explain
the `1000`, an examiner may ask.

**Say:**
> This is the throughput model. estimate_required_nodes turns an average latency into a
> service rate. Latency is how long one request takes; the service rate is how many
> requests a node finishes per second, which is just the reciprocal. The latency is in
> milliseconds, so a thousand divided by it gives requests per second. A node that averages
> eight seconds per request handles about an eighth of a request per second. We then divide
> the incoming request rate by that and round up, that's how many nodes the load needs, and
> subtract the nodes already on. One detail: avg_llama_latency_ms is the per-node inference
> time, the time actively spent processing, which matches how the report defines service
> time.

---

## Slide 24 — Turn on nodes, continued (latency feedback)

**Status:** Good. This is the second signal. Know the worked example, and know the
code-vs-report nuance for Q&A (see bottom).

**Say:**
> This is the latency safety signal. The throughput model assumes a node's service rate
> stays constant, but under concurrency requests slow each other down, so we also watch
> measured latency directly. If the average latency is above the maximum allowed, we take
> the ratio of the two as a scale factor and grow the current node count by it. For example,
> if two nodes are on and latency is double the limit, the scale factor is two, so we want
> four nodes, and we add two. If latency is under the limit, this signal asks for nothing
> and the throughput model decides. Back on the previous concept slide, we take the max of
> these two.

---

## Slide 25 — Turn off nodes

**Status:** Good, the two-bullet phrasing is much clearer than before. It's a bit thin,
and it currently ends your section with no wrap-up. Two suggestions below.

**Change 1 (optional):** add one execution bullet so the turn-off story is complete:
- "Cluster API executes the shutdown safely: keeps one node alive, won't power off a node
  mid-request, graceful SSH shutdown."

**Change 2 (recommended):** add a short closing slide after this (see below) instead of
jumping straight into your live demo.

**Say:**
> Scaling down is driven by idle time: a node idle past a configurable threshold becomes a
> candidate for shutdown. But there's a guard at the cluster level: if the cluster's average
> latency is above the limit, we skip the entire turn-off pass. That matters because a node
> can look idle while the cluster is actually overloaded, for instance a node we just powered
> on that hasn't received traffic yet, so we never shed capacity while we're slow. The actual
> shutdown is carried out by the cluster API, which keeps one node permanently alive and never
> powers off a node that still has requests in flight.

---

## Recommended new closing slide — Scoring and the power scheduler are coupled

**Status:** New. A strong closing beat that makes your two components feel like one design,
and it sets up your live demo (you launch a test, then walk the room to the hardware).

**On the slide:**
- Extra nodes are added to clusters **in scoring order** → under carbon-first, capacity
  grows on the **greenest** cluster first
- More active nodes → higher load → lower renewable fraction → slightly worse carbon score
- Negative feedback: self-limiting, not runaway

**Say:**
> One last point that ties both of my components together. When the power scheduler adds
> nodes, it adds them to clusters in the order cluster selection ranks them. So under
> carbon-first, capacity grows on the greenest cluster first, the same one the scorer
> already favors. And there's a loop the other way: turning more nodes on raises a cluster's
> power draw, which lowers its renewable fraction, which slightly worsens its carbon score.
> That's negative feedback, so it's self-limiting. The two decisions, where to send work and
> how much capacity to have, are really one coordinated system. Rather than just tell you it
> works, let me show you. I'll start a real test on the framework now, and while it runs we'll
> go look at the actual hardware it's running on.

> **→ Then:** live demo (start a test on the frontend), walk to the hardware, return, and
> Mads resumes with the full-run results. See the demo runbook for the click-by-click flow.

---

## Q&A ammunition (know these, don't put them on slides)

- **Why does avg_llama_latency_ms (inference) feed the latency signal, when the report says
  end-to-end?** Real divergence to have a stance on. The throughput model correctly uses
  inference latency (matches the report's "service time, excluding waiting"). But the
  latency-feedback term `S = L_obs/L_max` is fed inference latency in the code
  (`power_scheduler.py:310-313`), whereas the report (eq 10) defines `L_obs` as end-to-end.
  Scale-down uses end-to-end (`:365`). Present it per the report; if pushed, either justify
  the asymmetry or call it a minor inconsistency you'd reconcile.
- **What stops it from powering off a busy node?** Two layers in the cluster API: nodes with
  in-flight requests are filtered out before selection (`:488`), and after a node is marked
  TURNING_OFF it sleeps 10s and re-checks, aborting back to IDLE if a request arrived
  (`:95-104`).
- **How is "at least one node" guaranteed?** The keeper: the lowest-named node is excluded
  from the shutdown loop (`:471-477`), so one specific node always stays on, plus a `stay_one`
  fallback that prevents dropping to zero.
- **Why max of the two scale-up signals, not sum?** They estimate the same total from
  different assumptions; sum double-counts and over-provisions, max covers the binding
  constraint.
- **Why is the turn-off latency guard not redundant with the idle threshold?** Idle is
  per-node; the latency guard is per-cluster. The router deliberately keeps some nodes idle so
  they can power down, so an idle node can coexist with an overloaded cluster.
