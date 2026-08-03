# Drift Detection Methods — Mathematical Reference

> Implementation reference for `sentinel/detectors/`. Covers the theory behind each method, implementation choices, and known limitations.
>
> Nothing here is implemented yet — this is the specification the implementation is written against.

---

## 0. Temporal Split — What the Dataset Actually Supports

Design constraint that shapes every experiment below, stated first because getting it wrong invalidates everything downstream.

IEEE-CIS provides **no calendar dates**. `TransactionDT` is an integer offset in seconds from an undisclosed reference point. The labeled file `train_transaction.csv` spans roughly **182 days** (~6 months, to be confirmed in Phase 0 via `TransactionDT.max() / 86400`). The `test_transaction.csv` split covers the subsequent period but ships **no `isFraud` column**, so it cannot support any performance measurement.

Practical consequences:

- All windows are **day offsets within the labeled period**, never calendar months
- The usable timeline is ~6 months, not 12 — roughly 4–5 evaluation batches after carving out a reference window
- Reference window must be long enough to train a usable model *and* leave enough batches for detection to be measurable. Provisional split: days 0–59 reference, then 30-day batches
- If Phase 0 shows drift is weak across 182 days, 14-day batches trade per-batch statistical power for more batches — relevant because Table 3's denominator is the number of batches

**Sample-size interaction.** Batch size directly affects two detectors in opposite directions: KS has low power below n≈100, so batches must not get too small; MMD is O(n²) and gets subsampled to n=2000 anyway, so it is indifferent to batches above that size. Batch boundaries are therefore a real experimental parameter, not an arbitrary choice, and whatever is picked gets recorded with its justification.

---

## 1. PSI — Population Stability Index

### What it measures
Feature-level distribution shift between a reference dataset and an incoming batch. Originally developed for credit scoring model monitoring.

### Formula

```
PSI = Σ (actual_i - expected_i) × ln(actual_i / expected_i)
```

Where `actual_i` is the fraction of incoming data in bin `i`, and `expected_i` is the fraction of reference data in bin `i`.

### Interpretation

| PSI Score | Interpretation |
|---|---|
| < 0.10 | No significant change |
| 0.10 – 0.20 | Moderate shift — investigate |
| > 0.20 | Significant shift — flag for retraining |

### Implementation choices
- Bins: 10 equal-frequency bins derived from reference distribution (not equal-width — equal-frequency handles skewed distributions better, which fraud data always has)
- Smoothing: add ε = 0.0001 to avoid log(0) on empty bins
- Applied per feature; report max PSI and mean PSI across all features

### Limitation
Univariate — runs independently on each feature. Does not catch joint distribution shifts where individual features look stable but their correlation structure has changed.

---

## 2. KS Test — Kolmogorov-Smirnov Test

### What it measures
Whether two samples come from the same continuous distribution. Non-parametric — no assumption about distribution shape.

### Formula

```
D = max|F_reference(x) - F_incoming(x)|
```

Where F is the empirical CDF. The test statistic D is the maximum absolute difference between the two empirical CDFs.

### Implementation choices
- Applied per feature using `scipy.stats.ks_2samp`
- Bonferroni correction for multiple comparisons: threshold p-value = 0.05 / n_features
- Report: flagged features, D statistic per feature, corrected p-value

### Limitation
Same as PSI — univariate. Also: the KS test has low power for small sample sizes (n < 100 per batch), which may be a constraint on small incoming batches.

---

## 3. MMD — Maximum Mean Discrepancy

### What it measures
Multivariate distribution shift in kernel-induced feature space. Catches joint distribution changes that PSI and KS miss — e.g., two features whose individual distributions are stable but whose correlation has flipped.

### Formula

```
MMD²(P, Q) = E[k(x, x')] - 2E[k(x, y)] + E[k(y, y')]
```

Where x, x' ~ P (reference), y, y' ~ Q (incoming), and k is a kernel function.

### Kernel choice
RBF (Radial Basis Function) kernel:
```
k(x, y) = exp(-||x - y||² / (2σ²))
```

Bandwidth σ set using the median heuristic: `σ = median(||x_i - x_j||)` over reference samples. This is a standard, parameter-free choice that works well in practice.

### Implementation choices
- Subsample to n=2000 per dataset if batches exceed this (MMD is O(n²) — needed for CPU feasibility)
- Use unbiased MMD estimator (Gretton et al. 2012)
- Permutation test (500 permutations) to get p-value
- Implemented in Numpy/Scipy — no GPU required at this scale

### Limitation
Slower than PSI/KS. Kernel choice affects sensitivity. Permutation test adds compute. May miss drift in very high-dimensional spaces without dimensionality reduction preprocessing.

---

## 4. Ensemble Detector

### Logic
Weighted vote across PSI, KS, and MMD verdicts.

```python
drift_detected = (
    w_psi * (psi_score > psi_threshold) +
    w_ks  * (ks_flagged_count > ks_count_threshold) +
    w_mmd * (mmd_pvalue < mmd_alpha)
) >= vote_threshold
```

Default weights: `w_psi = 1, w_ks = 1, w_mmd = 1` (equal). Default vote threshold: 2 out of 3.

### Rationale — stated as hypothesis, not result
- PSI alone misses multivariate shift
- KS alone misses joint correlation changes
- MMD alone has higher compute cost and may overfire on small samples
- **Hypothesis:** requiring 2/3 agreement reduces false positives versus any single method

### Why this may not work

Majority voting is not free improvement. It helps when constituent errors are *independent*; it does not when they are correlated — and PSI and KS are both univariate tests over the same features, so their errors are strongly correlated by construction. The ensemble is effectively a 2-vote system with one and a half opinions.

Two specific failure modes to watch for:

1. **Precision gain paid for in recall.** Requiring agreement suppresses false positives *and* genuine early warnings. If MMD alone catches a joint shift that PSI and KS structurally cannot see, the 2-of-3 rule vetoes the one detector that was right.
2. **Landing between constituents.** The common outcome for majority votes over correlated members: worse than the best member, better than the worst, useful only if you did not know which member was best.

Both are testable against Table 3. If the ensemble's alert precision does not exceed the best single detector's, that gets reported plainly — a null result on the ensemble is still a finding, and a more interesting one than another PSI implementation.

### Ablation
Run 1-of-3, 2-of-3, and 3-of-3 vote thresholds and report all three. The vote threshold is the ensemble's only real degree of freedom; showing the full sweep prevents cherry-picking whichever value happened to look best.

### Configurable parameters
- `--psi-threshold` (default: 0.20)
- `--ks-count-threshold` — number of features that must be flagged (default: 3)
- `--mmd-alpha` — significance level (default: 0.05)
- `--vote-threshold` — methods required to agree (default: 2)

---

## 5. ADWIN (Future — Not Implemented)

Adaptive Windowing maintains a sliding window over an error rate stream. When the error rate in the recent half of the window differs significantly from the earlier half (by more than a threshold derived from Hoeffding's inequality), it declares drift and shrinks the window.

Requires ground-truth labels — in a fraud context, this means confirmed fraud outcomes from the investigation team, which typically arrive days or weeks after the prediction. This delayed feedback makes ADWIN complementary to input-space methods (PSI/KS/MMD), not a replacement.

Reference: Bifet & Gavaldà 2007, "Learning from Time-Changing Data with Adaptive Windowing."

---

## Notes on Evaluation Methodology

### Alert Precision — the core evaluation

Every detector in this project answers "has the input distribution shifted?" — but the question that matters operationally is "will my model get worse?" These are not the same question, and the gap between them is what Table 3 measures.

**Construction.** Each detector emits a binary verdict per batch. Treat that verdict as a *prediction* of the event "this batch's PR-AUC falls at least δ below the reference baseline." Then:

```
alert precision = (alerts on degraded batches) / (total alerts fired)
alert recall    = (alerts on degraded batches) / (total degraded batches)
```

Precision answers "when it cried drift, was anything actually wrong?" Recall answers "when things went wrong, did it notice?"

**Degradation threshold δ.** Fixed in Phase A, *before* any detector runs, to avoid choosing a threshold that flatters a particular method. Two candidate definitions, decided once Table 1 exists:

- **Absolute:** PR-AUC drops ≥ δ below the reference baseline (e.g. δ = 0.05)
- **Relative:** PR-AUC drops ≥ δ% of baseline, more robust if baseline PR-AUC is itself low

Whichever is chosen gets recorded here with its value, and the other is reported as a sensitivity check — if the ranking of detectors flips between the two, that instability is itself a finding.

**Small-sample caveat.** With only 4–5 batches, these are counts out of a handful, not stable rates. A single flipped batch swings precision by 20+ points. Two mitigations, both applied:

- Report raw counts alongside every ratio — `2/8` is honest in a way that `25.0%` is not
- Use finer batch granularity (14-day windows instead of 30-day) if Phase 0 shows the span supports it, trading batch size for a larger denominator

The Phase C engineered scenarios exist partly to address this: injected drift gives arbitrarily many batches with known ground truth, so detector sensitivity gets measured at a sample size the natural data cannot provide.

**Circularity check.** Detectors receive features only — never `isFraud`, never model predictions, never performance metrics. Labels enter exclusively in the scoring step, after alerts are already committed. Without that separation the number would be meaningless.

### What "samples before detection" means
Given temporally-ordered batches, how many cumulative incoming samples were processed before each detector first flagged drift? Lower = earlier warning. Only meaningful when compared against the batch where degradation actually occurs — a detector that alerts on batch 1 of 4 is "earliest" and also possibly just noisy, which is why this metric is never reported without Table 3 beside it.

### Trivial baselines
Two degenerate detectors are run alongside the real ones:

- **Never-alert** — precision undefined, recall 0%. The status quo of scheduled retraining.
- **Always-alert** — recall 100%, precision equal to the base rate of degraded batches.

Any real detector must beat always-alert on precision to be worth running. This sounds obvious but is exactly the comparison most drift-detection writeups omit.

### Multiple testing
KS runs one test per feature. With 400+ features in IEEE-CIS, a naive p=0.05 threshold gives ~20 false positives on stable data. Bonferroni correction is conservative but appropriate here — the cost of a false alert (unnecessary retraining) is lower than the cost of a missed detection.

Note the asymmetry this creates in Table 2: PSI has no multiple-testing correction because it produces a score rather than a p-value, so KS is held to a stricter standard than PSI by construction. This is documented rather than corrected, because both are being compared *as practitioners actually use them*.

### Why PR-AUC over ROC-AUC
IEEE-CIS is roughly 3.5% fraud. Under imbalance that severe, ROC-AUC is dominated by true negatives and stays high even as the model's ranking of the positive class deteriorates — precisely the failure mode of interest. PR-AUC is sensitive to exactly that (Davis & Goadrich 2006). ROC-AUC is still reported, for comparability with published IEEE-CIS baselines which conventionally use it.

One consequence: the degradation threshold δ is defined on PR-AUC, so Table 3 may show degraded batches where ROC-AUC looks stable. That divergence is worth calling out in the writeup rather than smoothing over.

### Why not just track model performance directly?
Because it requires ground-truth labels for every incoming prediction. In real deployments labels are delayed (fraud confirmed days or weeks later) or never arrive (benign transactions are rarely reviewed). Input-space drift detection needs no labels — that is its entire practical advantage, and the reason its reliability is worth measuring carefully.

This project has labels for the full window, which is a luxury production does not have. That luxury is spent on *evaluating* the label-free methods, not on helping them.

### Reproducibility
Every stochastic step is seeded and the seed recorded in the run's JSON summary: MMD subsampling, MMD permutation test, LightGBM training, and any engineered-drift injection. A rerun on the same data must reproduce every table cell exactly.
