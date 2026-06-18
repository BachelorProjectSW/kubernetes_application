# Stats & results defense — drill before the exam

Covers the "did you do enough analysis / statistical testing?" line of questions (your
supervisor flagged **non-parametric tests** and **"zeta"/z-testing**). Goal: explain the terms,
concede the gap honestly, and show statistical maturity. Drill the bold bits and the two
verbatim answers at the bottom.

> "Zeta testing" is almost certainly **z-test (z-testing)** — there's no standard method called
> "zeta testing." Treat it as the z-test (a parametric test). Flag if your supervisor clearly
> meant something else.

---

## 1. The terms, in plain language

- **Parametric tests** (z-test, t-test, ANOVA): **assume the data is roughly normal** (a bell
  curve) and compare **means**. A **z-test** compares means for large samples / known variance.
  Powerful *only when the normality assumption holds*.
- **Non-parametric tests** (Mann-Whitney U, Kruskal-Wallis, Wilcoxon): **assume no particular
  distribution**; compare distributions/medians by **ranking** the data. Use when data is
  **skewed, has outliers, or isn't normal**.
- **What any of them buy you:** instead of "carbon-first averaged 46 gCO₂, latency-first 98,"
  you test whether that difference is **statistically real or just run-to-run noise**. Your
  Test 1 vs Test 2 repeatability runs prove noise exists, so the question is fair.

| | Parametric (z-test / t-test) | Non-parametric (Mann-Whitney U / Kruskal-Wallis) |
|---|---|---|
| Assumes normal data? | **Yes** | **No** |
| Compares | means | distributions / medians (via ranks) |
| Good for | symmetric, bell-shaped data | **skewed data with outliers (= latency)** |

---

## 2. Why the supervisor said *non-parametric* specifically (the key insight)

**Latency is heavily right-skewed:** most requests are fast, but some are very slow or time out
around ~20000 ms. That long tail **breaks the normality assumption**, so a z-test/t-test on
latency would be statistically shaky. A non-parametric test handles skew without assuming
normality, so it's the **correct tool for latency**:
- **Mann-Whitney U** → compare **two** groups (e.g. carbon-first vs latency-first latency).
- **Kruskal-Wallis** → compare **all three** weight configs at once.

That is *exactly* why the supervisor pointed at non-parametric rather than the parametric z-test.

---

## 3. Would it have made sense? Where it matters most

- **Latency comparisons → YES, most valuable.** Effects are smaller (9436 vs 11227 ms) and the
  data is noisy/skewed; a non-parametric test would show whether the difference is significant
  or within noise.
- **Carbon / cost → less critical.** Effects are huge (~53% cut, 98→46 gCO₂); significance is
  visually obvious. A test would confirm, not reveal.

So a non-parametric test would have **strengthened the latency claims**; the headline carbon/cost
findings are robust on effect size alone.

---

## 4. The honest state of your analysis

- You did **descriptive / point comparisons** (means + % differences), **not inferential
  statistics** (hypothesis tests, p-values). Real gap; you *have* the per-request data to do it.

## 5. The deeper caveat (say it first — it shows maturity)

- Per-request observations **within one run are NOT independent**: under load, requests queue and
  their latencies correlate. Treating 2880 requests as 2880 independent samples would
  **overstate significance** ("pseudo-replication").
- The clean unit of replication is the **run**, and you have only **2 runs per condition**, too
  few for run-level statistics.
- So doing it *properly* needs **more independent runs** (≈5–10 per config), not just a test on
  the existing data. This is the real reason rigorous testing wasn't feasible as-is.

---

## 6. "Not enough results data?" — separate volume from breadth

- **Volume (per-request):** adequate. 2880 requests × several runs × 6 h is plenty at the
  request level.
- **Breadth + replication:** the real limit, only **2 clusters / 2 countries, one main
  workload, 8 rpm, 2 repeats per condition.** Already listed in the paper's limitations. The
  missing statistics sit on top of this: limited replication is *why* significance testing
  wasn't really feasible.

Frame: **data volume is fine; the experimental design (few conditions/repeats) and absence of
inferential statistics are acknowledged limitations**, fixed by more runs + non-parametric tests.

---

## 7. Two verbatim answers to memorize

**"Did you do significance testing / enough analysis?"**
> "We reported descriptive comparisons rather than significance tests. For the latency results
> specifically, a non-parametric test like **Mann-Whitney U** (or Kruskal-Wallis across the three
> configs) would have been the right choice, because latency is heavily right-skewed with timeout
> outliers, so it violates the normality assumption a z-test or t-test relies on. We'd add that as
> future work, together with more independent runs per configuration, since two repeats isn't
> enough for run-level statistics and per-request samples within a run aren't independent."

**"Would it have changed your conclusions?"**
> "For carbon and cost, no, the effects are large enough to be unambiguous. For latency, a test
> would tell us whether the smaller differences are significant or within noise, which is genuinely
> worth knowing, so that's where it would have added the most."

---

## 8. One-line takeaway
> Volume of data is fine; what's missing is **inferential statistics** and **replication**. The
> right tool is a **non-parametric test (Mann-Whitney U / Kruskal-Wallis)** because **latency is
> skewed**, not a parametric z-/t-test. Concede it, name the right test and *why*, and point to
> more runs as future work.
