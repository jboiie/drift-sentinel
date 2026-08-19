# Drift Sentinel — Resource-Constrained Build Plan

> What actually gets built, given a student laptop, no budget, and evenings after coursework. Scoped so it finishes.

---

## Constraints

- **Hardware**: laptop, 8GB RAM, CPU only — no GPU
- **Budget**: ₹0. Free-tier everything.
- **Time**: ~4–5 weeks alongside coursework
- **Dataset**: IEEE-CIS Fraud Detection (Kaggle, free download, ~500MB)

---

## What Gets Cut vs PRD

| PRD Feature | This Build | Reason |
|---|---|---|
| ADWIN concept drift | Documented limitation, not built | Requires live label feedback — delayed ground truth not available in batch replay |
| Online retraining loop | Out of scope | The project is about detection, not remediation |
| Multi-model adapter | LightGBM only | Keeps scope tight; adapter pattern documented for extension |
| Real-time streaming | Batch replay | Batch answers every question here; streaming adds infra complexity and no new numbers |
| Kubernetes | Nothing | Nothing in this project needs an orchestrator |
| **FastAPI model server** | **Cut to stretch** | Changes no table. Batch replay answers everything offline |
| **Streamlit dashboard** | **Replaced, and promoted to Phase D** | Built as a static Plotly site on GitHub Pages instead — no cold start, no hosting, same charts |
| **SQLite / Supabase prediction log** | **Cut to stretch** | Only needed by the server that was cut. Batches are CSVs on disk, run output is JSON |

### On cutting the deployment layer

The server, dashboard, and prediction log were roughly a week of the original four. None of them move a number in Tables 1–4. That week buys the alert-scorer work in Phase B — the only part of this project that isn't already in a hundred other drift-detection repos.

The tradeoff is real, and it cuts differently for a portfolio project: something someone can *click* beats a table of numbers, every time.

So the dashboard came back — as Phase D, not as a stretch goal, and not as Streamlit. A static Plotly site published to GitHub Pages costs a fraction of a Streamlit Cloud deployment to maintain (nothing to maintain), never sleeps, and reuses the Jinja2 + Plotly generator Phase C needs anyway. The FastAPI server stays cut: it is the half of the deployment layer that produces nothing to look at.

Phase D is deliberately last. It reads `reports/*.json` and renders — it computes nothing. That ordering means a dashboard slipping cannot damage Tables 1–4, and a Phase D that runs out of time still ships panels 1 and 2, which carry the argument on their own.

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

The null outcome is not a failure. "IEEE-CIS shows no detectable natural drift over its labeled window, so detector comparison requires engineered drift" is a perfectly good thing to have found out — and finding it on day 1 costs two hours instead of three weeks.

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

### Phase B — Detectors + Alert Precision (Week 2) ← the part worth showing

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

**External baselines:** NannyML and Evidently on the identical batches. Numbers that only compare against themselves prove nothing; third-party implementations are what make the comparison mean something.

Order matters within this phase: build `alert_scorer` **early**, not last. It is the one thing that makes this project distinctive, and leaving it to the final day is exactly how it becomes the thing that gets cut.

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

### Phase D — Dashboard (Week 4)

**Goal:** make the results visible in one screen, at a URL that loads instantly and never sleeps.

Nothing here computes anything. Phase D reads the JSON that Phases A–C already wrote and renders it, which is why it is safe to put last: if it slips, the numbers are unaffected.

Deliverables:
- `sentinel/dashboard.py` — `reports/*.json` → self-contained static site in `docs/`
- `sentinel/templates/dashboard.html.j2` + `style.css` — one template, one stylesheet, Plotly inlined, no CDN and no JS framework
- Six panels, in strict build order:
  1. **Panel 2 — PR-AUC over time with alert markers overlaid.** Built *first*, because it is the chart the entire project argues for. If nothing else ships, this does
  2. Panel 1 — alert precision/recall scoreboard with baselines, oversized stat tiles
  3. Panel 5 — detector × scenario heatmap, batches-to-detection, null-control column blank
  4. Panel 3 — per-detector drift score timelines as small multiples with threshold lines
  5. Panel 4 — reference vs incoming feature distributions, batch selectable
  6. Panel 6 — run provenance: seeds, boundaries, dataset span, versions
- Dark theme default, light via `prefers-color-scheme`, responsive down to phone width
- GitHub Pages enabled on `main` → `/docs`; cold load verified under one second
- Panels 1, 2, 5 exported to PNG and embedded in the README

**Hard rule, same as the README's:** every number rendered comes from a JSON file the pipeline wrote. Nothing is typed into a template by hand.

Stack: Jinja2, Plotly, Kaleido (PNG export). No new services, no hosting bill.

---

### Week 5 — Writeup and Buffer

No new components. Absorbs overruns from Phases 0–D, which is what actually happens to final-week plans.

Deliverables:
- All four tables populated with real numbers
- README lede rewritten around the measured result — including if the result is "detectors don't predict degradation on this dataset"
- Key Takeaways written per phase, unflattering results included
- Dashboard URL live and linked from the README badge
- `prior_work.md` finalized

**If and only if everything above is done early:** the FastAPI `/predict` + `/health` server and SQLite prediction log. Specified in `prd.md`. Adds no numbers and nothing visual — genuinely optional.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Only ~182 days of labeled data, not 12 months** | **Certain** | Already absorbed: day-offset batches, not calendar months. Phase 0 confirms exact span before boundaries are fixed |
| **Too few batches for stable alert precision** | **High** | Report raw counts beside every ratio; drop to 14-day batches if span allows; Phase C engineered scenarios supply the large-N sensitivity numbers |
| IEEE-CIS natural drift too small to detect | Medium | Phase 0 decision gate catches this on day 1; Phase C engineered drift becomes primary experiment |
| MMD too slow on CPU for large batches | Medium | Subsample to n=2000 per side, fixed seed; PSI/KS run on full batch |
| Ensemble adds nothing over best single detector | **Medium-high** | Expected outcome, not a failure. Report it plainly, with the vote-threshold comparison showing why |
| 8GB RAM insufficient for 400+ float64 columns | Medium | float32 downcast on load; drop columns above a missingness threshold; checked in Phase 0 |
| LightGBM overfits reference window | Low | Early stopping on a *temporal* validation slice — never a random split, which leaks future data |
| NannyML/Evidently produce identical results to ours | Low | Fine result: "hand-rolled detectors match the production libraries" — report it as-is |
| Scope creep back into the deployment layer | Medium | Only the dashboard came back, as Phase D. The FastAPI server stays deferred and is not started until all four tables are populated |
| Phase D dashboard eats the buffer week | Medium | Phase D computes nothing, so slipping it costs no results. Panel 2 is built first; a half-finished Phase D still ships the chart that carries the argument |

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
- Dashboard live at `jboiie.github.io/drift-sentinel`, cold-loading in under a second, every number on it generated from pipeline JSON

Test count is deliberately not a target. Coverage of the detector math and the scoring logic is what matters; "48+ tests" measures typing, not correctness.
