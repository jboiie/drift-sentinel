# Drift Sentinel — Resource-Constrained Build Plan

> What actually gets built, given a student laptop and no budget. Scoped to produce real, defensible findings.

---

## Constraints

- **Hardware**: laptop, 8GB RAM, CPU only — no GPU
- **Budget**: ₹0. Free-tier everything.
- **Time**: ~3–4 weeks alongside coursework
- **Dataset**: IEEE-CIS Fraud Detection (Kaggle, free download, ~500MB)

---

## What Gets Cut vs PRD

| PRD Feature | This Build | Reason |
|---|---|---|
| ADWIN concept drift | Documented limitation, not built | Requires live label feedback — delayed ground truth not available in batch replay |
| Online retraining loop | Out of scope | Research question is detection, not remediation |
| Multi-model adapter | LightGBM only | Keeps scope tight; adapter pattern documented for extension |
| Real-time streaming | Batch replay | Batch covers all research questions; streaming adds infra complexity with no finding benefit |
| Kubernetes | Nothing | No deployment on the findings path at all |
| **FastAPI model server** | **Cut to stretch** | Changes no table. Batch replay answers every research question offline |
| **Streamlit dashboard** | **Cut to stretch** | Static HTML report already makes results sharable |
| **SQLite / Supabase prediction log** | **Cut to stretch** | Only needed by the server that was cut. Batches are CSVs on disk |

### On cutting the deployment layer

The server, dashboard, and prediction log were roughly a week of the original four. None of them move a number in Tables 1–4. That week buys the alert-scorer work in Phase B, which is the only part of this project that produces a finding not already in a hundred other drift-detection repos.

The tradeoff is real: a live `/predict` endpoint is a visible deployment-skills signal. The judgement here is that one defensible finding beats one more CRUD API, and the deployment layer stays specified so it can be added later if Phases 0–C land early.

---

## Phase Build Order

### Phase 0 — Premise Validation (Day 1, ~2 hours)

**Goal:** confirm the project's core assumption before spending a week on it.

Every table downstream assumes two things: that the labeled window is long enough to split meaningfully, and that the model measurably degrades across it. Both are checkable in an afternoon with pandas alone.

Deliverables:
- Download IEEE-CIS, load `train_transaction.csv`
- `TransactionDT.max() / 86400` → confirm the actual day span
- Fraud rate per 30-day bucket → is the class prior stable?
- `TransactionAmt` and 3–4 high-importance `V*` distributions per bucket → is there visible shift?
- Memory check: confirm the frame fits in 8GB after float32 downcast

**Decision gate:**

| Phase 0 outcome | Consequence |
|---|---|
| Visible natural drift across the window | Phases A–C proceed as written |
| Span shorter than expected | Shrink to 14-day batches, revise all boundaries before Phase A |
| No meaningful natural drift | Phase C engineered drift becomes the *primary* experiment; Phase A reports the null honestly |
| Frame doesn't fit in memory | Column-drop by missingness threshold before anything else |

The null outcome is not a failure. "IEEE-CIS shows no detectable natural drift over its labeled window, so detector comparison requires engineered drift" is a legitimate, publishable framing — and finding it on day 1 costs two hours instead of three weeks.

Stack: Pandas, Matplotlib. Nothing else installed yet.

---

### Phase A — Model + Baseline Degradation (Week 1)

**Goal:** quantify how much the model degrades across the labeled window.

Deliverables:
- `scripts/prepare_data.py` — temporal split (reference window + ordered batches, boundaries set by Phase 0)
- `scripts/train_model.py` — LightGBM on the reference window, early stopping on a *temporal* validation slice (never random split — random validation leaks future data and inflates the baseline)
- `notebooks/analysis.ipynb` — distribution plots per batch, class imbalance analysis
- Table 1 populated, PR-AUC primary
- **Degradation threshold δ fixed and written into methods.md** — before any detector exists, so it cannot be tuned to flatter one

Stack: Pandas, LightGBM, Scikit-learn, Matplotlib.

---

### Phase B — Detectors + Alert Precision (Week 2) ← the core contribution

**Goal:** implement the detectors, then measure whether their alerts predict real degradation.

Deliverables:
- `sentinel/detectors/base.py` — one interface: `score(reference, incoming) → (statistic, verdict)`
- `sentinel/detectors/psi.py` — PSI, equal-frequency bins from reference
- `sentinel/detectors/ks_test.py` — per-feature KS with Bonferroni correction
- `sentinel/detectors/mmd.py` — RBF kernel, median-heuristic bandwidth, permutation test, subsample n=2000
- `sentinel/detectors/ensemble.py` — k-of-n vote, with 1/2/3 threshold ablation
- `sentinel/runner.py` — CLI entrypoint, stdout + JSON drift log
- `sentinel/evaluation/alert_scorer.py` — **joins drift log to performance log, produces Table 3**
- `tests/test_detectors.py` — synthetic data, no Kaggle dependency: identical distributions must not flag, shifted ones must
- `tests/test_alert_scorer.py` — precision/recall arithmetic on hand-checked inputs
- Tables 2 and 3 populated

**Trivial baselines:** never-alert and always-alert run alongside. Any detector failing to beat always-alert on precision has earned nothing.

**External baselines:** NannyML and Evidently on the identical batches. Self-referential numbers are worthless; third-party implementations are what make the comparison defensible.

Order matters within this phase: build `alert_scorer` **early**, not last. It is the deliverable that distinguishes this project, and leaving it to the final day is how it becomes the thing that gets cut.

Stack: Scipy, Numpy, NannyML, Evidently.

---

### Phase C — Engineered Drift + HTML Report (Week 3)

**Goal:** inject controlled drift with known ground truth. Measure detector sensitivity by drift type.

This phase also fixes Phase B's sample-size problem: natural data gives 4–5 batches, engineered data gives as many as needed, so detector sensitivity gets measured at a denominator that supports actual conclusions.

Deliverables:
- `scripts/simulate_drift.py` — five modes:
  - `--mode gradual` — linearly shifts a feature distribution over N batches
  - `--mode sudden` — step-changes a feature distribution at batch K
  - `--mode prior` — shifts class imbalance ratio
  - `--mode covariate` — flips correlation between 2+ features while holding marginals fixed (the case PSI and KS structurally cannot see)
  - `--mode null` — **control: injects nothing.** Any alert here is a false positive under known ground truth
- `sentinel/report.py` — static HTML report (Jinja2 template, self-contained)
- `--fail-above` flag on runner (exit code 1 if ensemble drift score exceeds threshold)
- Table 4 populated
- `notebooks/analysis.ipynb` extended with result visualizations

The null control is the cheapest row in the table and the most informative — it is the only place false positive rate is measured against certainty rather than assumption.

Stack: Jinja2, Plotly (embedded HTML charts).

---

### Week 4 — Writeup and Buffer

No new components. Week 4 absorbs overruns from Phases 0–C, which is what actually happens to week-4 plans.

Deliverables:
- All four tables populated with real numbers
- README lede rewritten around the measured result — including if the result is "detectors don't predict degradation on this dataset"
- Key Takeaways written per phase, null results included
- `prior_work.md` finalized

**If and only if everything above is done early:** the deferred deployment layer (FastAPI `/predict` + `/health`, SQLite prediction log, Streamlit dashboard). Specified in `prd.md`, off the findings path, strictly optional.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Only ~182 days of labeled data, not 12 months** | **Certain** | Already absorbed: day-offset batches, not calendar months. Phase 0 confirms exact span before boundaries are fixed |
| **Too few batches for stable alert precision** | **High** | Report raw counts beside every ratio; drop to 14-day batches if span allows; Phase C engineered scenarios supply the large-N sensitivity numbers |
| IEEE-CIS natural drift too small to detect | Medium | Phase 0 decision gate catches this on day 1; Phase C engineered drift becomes primary experiment |
| MMD too slow on CPU for large batches | Medium | Subsample to n=2000 per side, fixed seed; PSI/KS run on full batch |
| Ensemble adds nothing over best single detector | **Medium-high** | Expected outcome, not a failure. Reported as a null result with the vote-threshold ablation showing why |
| 8GB RAM insufficient for 400+ float64 columns | Medium | float32 downcast on load; drop columns above a missingness threshold; checked in Phase 0 |
| LightGBM overfits reference window | Low | Early stopping on a *temporal* validation slice — never a random split, which leaks future data |
| NannyML/Evidently produce identical results to ours | Low | That's a finding too: "hand-rolled detectors match production libraries" — publish honestly |
| Scope creep back into the deployment layer | Medium | It is specified and deferred. Not started until all four tables are populated |

---

## What "Done" Looks Like

- Phase 0 decision gate passed and its numbers recorded
- `python -m sentinel.runner --reference ... --incoming ... --output report.html` runs end-to-end
- All four Tables in README populated with real, reproducible numbers
- **Table 3 exists** — alert precision per detector, with raw counts shown
- Trivial baselines (never-alert, always-alert) present in the comparison
- NannyML *and* Evidently numbers present
- Null-control scenario reported: false positives measured against known ground truth
- `--fail-above` works (exit code 1 on threshold breach)
- Every stochastic step seeded; a rerun reproduces every cell
- README contains zero numbers that were not produced by running the code
- Tests cover the detectors and the alert-scorer arithmetic

Test count is deliberately not a target. Coverage of the detector math and the scoring logic is what matters; "48+ tests" measures typing, not correctness.
