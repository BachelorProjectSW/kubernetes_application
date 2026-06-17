# Jon — Read-Aloud Practice Script

> Just the words. Read it straight through to get the delivery in your mouth. Each block is
> one slide. The bracketed lines are stage directions, don't read those out loud.

---

**[Slide 16 — The Global Scheduler]**

This is the global scheduler, and it's where my two components live. It makes two decisions. Cluster selection decides, for each request, which cluster should serve it. The power scheduler decides how many worker nodes are powered on in each cluster. They run off the same data, the renewable output, carbon intensity, electricity price, latency, and the operator's weights, and as I'll show at the end, they're actually coupled. Let me start with cluster selection.

---

**[Slide 17 — Cluster Selection: Scoring Algorithm]**

Cluster selection runs once per request. Each cluster gets a score, a weighted sum of three normalized metrics: blended carbon intensity, blended electricity cost, and latency. The highest score wins. The weights are set by the operator and sum to one, so carbon weight one gives a carbon-first strategy, latency weight one gives latency-first, and equal weights is balanced. Because it's a weighted sum, we always get a single total order, so there's always exactly one best cluster to route to. The next slides explain what "blended" and "normalized" mean.

---

**[Slide 18 — Blending in the microgrid]**

Carbon and cost aren't used raw, they're blended against the microgrid's own production. The grid fraction is one minus renewable output over total cluster load, floored at zero. So if local solar covers half the load, the grid fraction is one half, and we multiply the grid's carbon intensity and its price by that fraction. The assumption is that locally produced renewable energy carries zero direct emissions and zero generation cost, so only the grid-supplied share counts. That's what makes a cluster in sunshine genuinely score cleaner and cheaper.

---

**[Slide 19 — Normalization]**

The three metrics have different units, so we map them to a common scale: one minus the value over a fixed reference maximum, the worst realistic value, floored at zero. A perfect cluster scores one, a cluster at the reference maximum scores zero. The reference maxima are 670 grams of CO2 per kilowatt-hour, 30 euro-cents, and 12 seconds. We chose fixed maxima over min-max normalization on purpose. With min-max, each metric is scored only relative to the clusters in front of you. Imagine cluster A at three cents and 500 grams, and cluster B at thirty cents and 450 grams. A is ten times cheaper for ten percent more carbon, clearly better, but min-max would score them both at one half and tie them. Fixed maxima keep the absolute scale, so A correctly wins. The trade-off is that these maxima are fixed values we picked, which Mads will come back to in the results.

---

**[Slide 20 — Data Sources]**

These metrics need real data, from three sources. PV production for the simulated clusters comes from the Pan-European Climate Database, hourly solar capacity factors from reanalysis weather data, times a fixed 1500-watt capacity. Carbon intensity and electricity prices come from Electricity Maps, and we use direct emission factors, because only generation emissions are relevant to a scheduling decision. For our real Danish cluster, live generation and consumption come from the CROM microgrid over a Tailscale VPN. And everything is anchored to simulated time, so every cluster is scored against the same simulated moment and the runs stay comparable and reproducible. That's cluster selection. Now the second decision, the power scheduler.

---

**[Slide 21 — Power Scheduler]**

The power scheduler keeps just enough nodes on to serve the load and powers the rest off to save energy. It runs as a periodic background loop, and each cycle it first decides whether to turn nodes on, then whether to turn idle nodes off. One hard invariant: at least one node always stays on in each cluster, so a cluster can never go fully dark and cluster selection always has a target. And the responsibility is split: the global scheduler decides how many nodes, and the cluster API actually executes the on and off. Let me show how it decides how many.

---

**[Slide 22 — Turn on nodes, the two signals]**

Scaling up uses two independent signals, and we take the larger of the two. The first, estimate nodes to add, is a throughput model: given the current request rate and how fast a node serves requests, how many nodes does the load need? The second, apply latency scaling, is a safety signal based on observed latency: if we're over the latency limit, it asks for more nodes regardless of the throughput estimate. We take the max because the two estimate the same thing, total nodes needed, from different assumptions. Summing them would double-count and over-provision; the max provisions for whichever constraint is actually binding. The next two slides show the actual code behind each of these.

---

**[Slide 23 — Turn on nodes, throughput model]**

This is the throughput model. Estimate required nodes turns an average latency into a service rate. Latency is how long one request takes; the service rate is how many requests a node finishes per second, which is just the reciprocal. The latency is in milliseconds, so a thousand divided by it gives requests per second. A node that averages eight seconds per request handles about an eighth of a request per second. We then divide the incoming request rate by that and round up, that's how many nodes the load needs, and subtract the nodes already on. One detail: this latency is the per-node inference time, the time actively spent processing, which matches how the report defines service time.

---

**[Slide 24 — Turn on nodes, latency feedback]**

This is the latency safety signal. The throughput model assumes a node's service rate stays constant, but under concurrency requests slow each other down, so we also watch measured latency directly. If the average latency is above the maximum allowed, we take the ratio of the two as a scale factor and grow the current node count by it. For example, if two nodes are on and latency is double the limit, the scale factor is two, so we want four nodes, and we add two. If latency is under the limit, this signal asks for nothing and the throughput model decides. And as I said, we take the maximum of these two estimates.

---

**[Slide 25 — Turn off nodes]**

Scaling down is driven by idle time: a node idle past a configurable threshold becomes a candidate for shutdown. But there's a guard at the cluster level: if the cluster's average latency is above the limit, we skip the entire turn-off pass. That matters because a node can look idle while the cluster is actually overloaded, for instance a node we just powered on that hasn't received traffic yet, so we never shed capacity while we're slow. The actual shutdown is carried out by the cluster API, which keeps one node permanently alive and never powers off a node that still has requests in flight.

---

**[Closing slide — Scoring and the power scheduler are coupled]**

One last point that ties both of my components together. When the power scheduler adds nodes, it adds them to clusters in the order cluster selection ranks them. So under carbon-first, capacity grows on the greenest cluster first, the same one the scorer already favors. And there's a loop the other way: turning more nodes on raises a cluster's power draw, which lowers its renewable fraction, which slightly worsens its carbon score. That's negative feedback, so it's self-limiting. The two decisions, where to send work and how much capacity to have, are really one coordinated system. Rather than just tell you it works, let me show you. I'll start a real test on the framework now, and while it runs we'll go look at the actual hardware it's running on.

**[→ Walk to the laptop, load the demo config, start the test, confirm it's running, then lead the room to the hardware.]**
