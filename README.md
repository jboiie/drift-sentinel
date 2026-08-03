<div align="center">

# 📉 Drift Sentinel

### ML Model Monitoring & Drift Detection Pipeline

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-design%20phase-orange.svg)]()

*Measuring whether drift detectors actually predict model failure — or just notice that the data moved.*

[Findings](#-findings) · [Pipeline](#-pipeline) · [Architecture](#-architecture) · [Drift Methods](#-drift-detection-methods) · [Quickstart](#-quickstart) · [Roadmap](#-roadmap)

</div>

---

> **The research question: does input-space drift detection actually predict model failure?**
>
> Drift detectors (PSI, KS, MMD) monitor the *input* distribution because production labels arrive late or never. But an input shift is not automatically a performance problem — a detector can fire on a harmless shift, or stay silent while accuracy collapses. Prior work ([Rabanser et al. 2019](https://arxiv.org/abs/1810.11953)) found this gap is large and method-dependent.
>
> Drift Sentinel replays a LightGBM fraud classifier over temporally-ordered IEEE-CIS batches, holding back labels from the detectors but using them for *evaluation*. Every alert is scored against realized degradation, producing an **alert precision** number per detector: of the times this method cried drift, how often did the model actually get worse?
>
> **No results yet.** All tables below are empty by design and get populated by running the pipeline. Any number in this README is either measured output or absent.

---

## 📌 The Problem

ML models degrade silently in production. A fraud classifier trained on January data will encounter December transaction patterns — different spending behaviors, new merchant categories, evolved fraud tactics — with no built-in mechanism to alert you that its predictions are becoming unreliable.

Most teams handle this with scheduled retraining: retrain every N days regardless of whether drift has actually occurred. This is both too slow (drift may happen in days, not months) and too expensive (retraining is costly when the model is still performing well).

The standard answer is drift detection: watch the *input* distribution, because labels arrive too late to watch the output. PSI, KS, and MMD are the usual tools, and every MLOps vendor ships some version of them.

But there is an assumption buried in that answer, and it is rarely tested: **that an input shift means a performance problem.** A detector can fire on a shift the model handles fine, and stay quiet while accuracy quietly collapses.

**Drift Sentinel measures that gap directly.** It replays a frozen fraud classifier over temporally-ordered batches, runs each detector label-free, then uses withheld labels to grade every alert after the fact:

1. **Does the model actually degrade** over the observed window? (Table 1)
2. **Which detector notices first**, and how often does it cry wolf? (Table 2)
3. **Do those alerts predict real harm?** — alert precision per detector (Table 3)
4. **Which drift types does each method miss** under known ground truth? (Table 4)

Table 3 is the one worth building the project for.

---

## 📊 Findings

> **Status: no experiments run yet.** Every cell below is a placeholder. Batch boundaries are provisional until [Phase 0](#phase-0--premise-validation-day-1) measures the dataset's actual time span.

### A note on the time axis

IEEE-CIS does not ship calendar dates. `TransactionDT` is an integer offset in seconds from an undisclosed reference point, and the labeled file (`train_transaction.csv`) covers roughly **182 days**, not a full year. The Kaggle test split covers the following period but is **unlabeled**, so it cannot be used for performance evaluation.

Consequently all windows below are expressed as **day offsets within the labeled period**, not months. Phase 0 verifies the true span before boundaries are fixed.

### Table 1 — Model Performance Degradation Over Time (Phase A)

*LightGBM trained on the reference window, evaluated on later held-out batches. No retraining.*

| Evaluation Window | PR-AUC | ROC-AUC | F1 (fraud) | Precision | Recall | Fraud rate | Δ PR-AUC vs baseline |
|---|---|---|---|---|---|---|---|
| Reference (days 0–59, train) | — | — | — | — | — | — | baseline |
| Batch 1 (days 60–89) | — | — | — | — | — | — | — |
| Batch 2 (days 90–119) | — | — | — | — | — | — | — |
| Batch 3 (days 120–149) | — | — | — | — | — | — | — |
| Batch 4 (days 150–181) | — | — | — | — | — | — | — |

**PR-AUC is the primary metric.** IEEE-CIS is ~3.5% fraud; ROC-AUC is inflated and insensitive at that imbalance. ROC-AUC is reported alongside for comparability with published baselines only.

### Table 2 — Detector Comparison (Phase B)

*How early does each method flag drift, and how often does it flag nothing at all?*

| Method | First Batch Flagged | Samples Before Perf. Drop | FP Rate (stable windows) | Runtime (n=5000) | Notes |
|---|---|---|---|---|---|
| Never-alert baseline | never | N/A | 0% | — | Lower bound: fixed-schedule retraining |
| Always-alert baseline | batch 1 | N/A | 100% | — | Upper bound: trivially "detects" everything |
| PSI | — | — | — | — | Univariate, binned |
| KS Test | — | — | — | — | Univariate, Bonferroni-corrected |
| MMD | — | — | — | — | Multivariate, RBF kernel |
| Ensemble (2-of-3 vote) | — | — | — | — | Hypothesis under test — see caveat below |
| NannyML (external) | — | — | — | — | Third-party reference implementation |
| Evidently (external) | — | — | — | — | Third-party reference implementation |

The two trivial baselines are included deliberately: any detector that cannot beat *always-alert* on precision and *never-alert* on recall has not earned its compute.

> **Ensemble caveat.** A 2-of-3 majority vote over detectors with differing false-positive profiles frequently lands *between* its constituents rather than above them. The ensemble is a hypothesis being tested here, not a claimed improvement. If it adds nothing over the best single detector, that result gets reported as-is.

### Table 3 — Alert Precision: Do Drift Alerts Predict Real Degradation? (Phase B)

*The core finding. Each detector's alerts are treated as predictions of "PR-AUC will drop in this batch," then scored against measured performance.*

| Detector | Alerts Fired | Alerts Preceding Real Degradation | **Alert Precision** | Degradations Missed | **Alert Recall** |
|---|---|---|---|---|---|
| PSI | — | — | — | — | — |
| KS Test | — | — | — | — | — |
| MMD | — | — | — | — | — |
| Ensemble | — | — | — | — | — |
| NannyML (external) | — | — | — | — | — |
| Evidently (external) | — | — | — | — | — |

Labels are used **only to score alerts after the fact** — never as detector input. The detectors remain label-free, which is the entire practical argument for input-space monitoring. See [methods.md](methods.md#alert-precision-the-core-evaluation) for the degradation threshold definition.

### Table 4 — Engineered Drift Scenarios (Phase C)

*Controlled drift injected into the stream. Measures detector sensitivity by drift type, with known ground truth.*

| Drift Scenario | Drift Type | PSI | KS | MMD | Ensemble | Batches to Detection |
|---|---|---|---|---|---|---|
| Gradual feature shift (transaction amount) | Covariate drift | — | — | — | — | — |
| Sudden distribution step at batch K | Covariate drift | — | — | — | — | — |
| Fraud rate doubled | Prior probability drift | — | — | — | — | — |
| Correlation flip between 2 features | Joint/covariate drift | — | — | — | — | — |
| **Null control** (no drift injected) | none | — | — | — | — | should be "never" |

The null control row measures false positives directly: any detector flagging the unmodified stream is producing a false alarm under known ground truth.

### Key Takeaways

*Populated after experiments run. Null and negative results are reported, not omitted.*

- **Phase A** — does the model measurably degrade over the labeled window?
- **Phase B** — which detector's alerts actually predict that degradation?
- **Phase C** — which drift types does each detector catch, and which does it miss?

---

## 🏗️ Architecture

Batch replay, not live serving. The experiment needs temporally-ordered batches scored by a frozen model — a network hop between the scorer and the detector would add infrastructure without changing a single number in any table.

```
   data/reference/          data/incoming/
   (days 0–59, labeled)     (batch_1 … batch_N, temporally ordered)
          │                        │
          │                        ├──────────────┐
          ▼                        ▼              │
╔══════════════════════════════════════════════╗  │
║          DRIFT ENGINE (label-free)           ║  │
║                                              ║  │
║   PSI ──┐                                    ║  │
║   KS  ──┼──▶ Ensemble vote ──▶ verdict       ║  │
║   MMD ──┘                                    ║  │
║                                              ║  │
║   Sees features only. Never sees isFraud.    ║  │
╚══════════════════════╤═══════════════════════╝  │
                       │ alerts                   │
                       │                          ▼
                       │            ┌──────────────────────────┐
                       │            │  Frozen LightGBM model   │
                       │            │  scores each batch       │
                       │            └────────────┬─────────────┘
                       │                         │ predictions
                       │                         ▼
                       │            ┌──────────────────────────┐
                       │            │  PERFORMANCE EVALUATOR   │
                       │            │  PR-AUC / ROC-AUC / F1   │
                       │            │  uses withheld labels    │
                       │            └────────────┬─────────────┘
                       │                         │ realized degradation
                       ▼                         ▼
          ╔══════════════════════════════════════════════════╗
          ║             ALERT SCORER  ← the finding          ║
          ║  Did each alert precede real degradation?        ║
          ║  ▶ alert precision / recall per detector         ║
          ╚═══════════════════════╤══════════════════════════╝
                                  ▼
                     HTML report + JSON summary
                     exit code 1 if --fail-above breached
```

The two halves are deliberately isolated: the drift engine is label-blind, and labels enter only downstream to grade the alerts it already emitted. That separation is what makes the alert-precision number honest rather than circular.

### Design Decisions

| Decision | Rationale |
|---|---|
| **Alert precision as the headline metric** | "We implemented PSI" is not a finding. "PSI fired 8 times and 2 preceded real degradation" is. Detecting input shift is only useful insofar as it predicts harm |
| **Batch replay over a live model server** | The research questions are all answerable offline. A FastAPI server changes no table and costs a week |
| **Labels withheld from detectors, used for scoring** | Preserves the practical claim (drift detection needs no labels) while still allowing alerts to be graded |
| **PR-AUC primary, ROC-AUC secondary** | ~3.5% positive class. ROC-AUC is optimistic and flat under that imbalance |
| **Trivial baselines in every comparison** | Never-alert and always-alert bound the problem. A detector that beats neither is noise with extra steps |
| **NannyML + Evidently as external baselines** | Self-referential numbers are worthless. Third-party implementations make the comparison externally anchored |
| **Ensemble as hypothesis, not conclusion** | Majority voting often underperforms its best member. Stated as a question the experiment answers |
| **Static HTML report output** | Sharable, no dashboard required. Drop the report into a PR comment or email it |

---

## 🔍 Drift Detection Methods

Nothing is implemented yet. Status column reflects build order, not progress.

| Method | What It Detects | Strength | Weakness | Status |
|---|---|---|---|---|
| **PSI** (Population Stability Index) | Distribution shift per feature | Industry standard, interpretable | Univariate only, requires binning | 🔲 Phase B |
| **KS Test** | Distribution shift per feature | Non-parametric, no binning | Univariate only, sensitive to sample size | 🔲 Phase B |
| **MMD** | Multivariate distribution shift in kernel space | Catches joint feature shifts KS/PSI miss | O(n²), kernel choice matters | 🔲 Phase B |
| **Ensemble** | 2-of-3 vote across PSI + KS + MMD | *Hypothesis:* fewer false positives | May land between constituents, not above | 🔲 Phase B |
| **NannyML / Evidently** | External reference implementations | Third-party, independently maintained | Not tuned to this dataset | 🔲 Phase B |
| **ADWIN** | Concept drift via sliding window on error rate | Reacts to actual performance drop | Requires ground truth labels (delayed) | ❌ Out of scope — see [Roadmap](#-roadmap) |

---

## 🚀 Pipeline

### Running the Monitor

> **Interface sketch — not yet built.** The shape below is the Phase B target, shown so the design is reviewable before implementation. Values are placeholders illustrating the output format, not measurements.

```bash
# Install
pip install -e ".[baselines,dev]"

# Run drift check on one incoming batch
python -m sentinel.runner \
  --reference data/reference/reference_window.csv \
  --incoming data/incoming/batch_04.csv \
  --model models/lgbm_fraud_ref.pkl \
  --output reports/batch_04_report.html \
  --fail-above 0.20
```

```
# =============================================
# DRIFT SENTINEL REPORT — batch_04
# =============================================
#   reference_size:      <n>
#   incoming_size:       <n>
#   psi_max / psi_mean:  <score> / <score>
#   ks_flagged_features: [<feature>, ...]   (Bonferroni-corrected)
#   mmd_statistic:       <score>  (p=<pval>, 500 permutations)
#   ensemble_verdict:    DRIFT | NO DRIFT   (<k>/3 detectors agree)
#   report:              reports/batch_04_report.html
# exit code 1 if ensemble drift score exceeds --fail-above
```

Note what the runner does **not** print: model performance. The detectors never see labels, so the runner cannot report a performance delta. That comparison happens separately in the evaluation step, which is exactly what keeps Table 3 honest.

### Evaluation Loop

```
   label-free path                        label-using path
   ───────────────                        ────────────────
   batch ──▶ detectors ──▶ alert?         batch ──▶ model ──▶ PR-AUC
                             │                                 │
                             └────────▶ ALERT SCORER ◀─────────┘
                                              │
                                    alert precision / recall
                                         (Table 3)
```

Every batch is logged with drift scores, flagged features, ensemble verdict, and — separately — realized performance. Joining those two logs produces Table 3 and provides the ground truth for the Phase C engineered scenarios.

---

## 📁 Project Structure

Target layout. Nothing below `sentinel/` exists yet — directories get created when the phase that needs them starts, not before.

```
drift-sentinel/
│
├── sentinel/                   ← CORE PIPELINE — primary entrypoint
│   ├── runner.py               # Main CLI: runs drift checks, outputs report
│   ├── detectors/
│   │   ├── base.py             # Detector interface (score → verdict)
│   │   ├── psi.py              # PSI, equal-frequency bins
│   │   ├── ks_test.py          # KS test, Bonferroni-corrected
│   │   ├── mmd.py              # MMD, RBF kernel + permutation test
│   │   └── ensemble.py         # k-of-n vote across detectors
│   ├── evaluation/
│   │   ├── metrics.py          # PR-AUC, ROC-AUC, F1 per batch
│   │   └── alert_scorer.py     # ← THE FINDING: alerts vs realized degradation
│   └── report.py               # Static HTML report generator
│
├── scripts/
│   ├── prepare_data.py         # Temporal split → reference + ordered batches
│   ├── train_model.py          # LightGBM on reference window, early stopping
│   └── simulate_drift.py       # Phase C: injects controlled drift scenarios
│
├── notebooks/
│   └── analysis.ipynb          # EDA, time-span validation, result plots
│
├── tests/
│   ├── test_detectors.py       # Synthetic data — no Kaggle dependency
│   └── test_alert_scorer.py    # Precision/recall logic on known inputs
│
├── data/                       # gitignored — download from Kaggle
│   ├── raw/                    # IEEE-CIS as downloaded
│   ├── reference/              # Reference window (days 0–59)
│   └── incoming/               # Ordered batches + engineered variants
│
├── models/                     # Serialized weights (gitignored)
├── reports/                    # Generated HTML/JSON (gitignored)
│
├── methods.md                  # Mathematical detail on PSI, KS, MMD, scoring
├── prd.md                      # North-star vision (explicitly aspirational)
├── prior_work.md               # Predecessor projects in the series
├── resource.md                 # Build plan under real constraints
├── pyproject.toml
├── .env.example
└── .gitignore
```

**Deferred (stretch, off the findings path):** `src/` FastAPI model server, `dashboard/` Streamlit app, SQLite prediction log. These demonstrate deployment skills but contribute nothing to Tables 1–4. Built only if Phases 0–C finish with time remaining.

---

## ⚡ Quickstart

> **Not runnable yet.** Steps below describe the intended flow; scripts are built in Phases 0–C.

### Prerequisites

- Python 3.10+
- ~2GB free disk (dataset is ~500MB compressed, larger unpacked)
- The IEEE-CIS Fraud Detection dataset from [Kaggle](https://www.kaggle.com/competitions/ieee-fraud-detection/data) (free, requires Kaggle account + accepting competition rules)

### 1. Clone and install

```bash
git clone https://github.com/jboiie/drift-sentinel.git
cd drift-sentinel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[baselines,dev]"
```

### 2. Prepare data

```bash
# Place train_transaction.csv and train_identity.csv in data/raw/
python scripts/prepare_data.py
# Prints the observed TransactionDT span, then writes:
#   data/reference/reference_window.csv
#   data/incoming/batch_01.csv … batch_NN.csv
```

Only `train_*.csv` is used. The Kaggle `test_*.csv` split has no labels and therefore cannot support performance evaluation.

### 3. Train the baseline model

```bash
python scripts/train_model.py
# LightGBM on the reference window with early stopping
# Saves models/lgbm_fraud_ref.pkl, prints baseline PR-AUC / ROC-AUC / F1
```

### 4. Run the drift monitor over all batches

```bash
python -m sentinel.runner \
  --reference data/reference/reference_window.csv \
  --incoming "data/incoming/batch_*.csv" \
  --model models/lgbm_fraud_ref.pkl \
  --output reports/ \
  --fail-above 0.20
```

### 5. Score the alerts against realized degradation

```bash
python -m sentinel.evaluation.alert_scorer \
  --drift-log reports/drift_log.json \
  --perf-log reports/performance_log.json
# Emits Table 3: alert precision and recall per detector
```

### 6. Run engineered drift scenarios (Phase C)

```bash
python scripts/simulate_drift.py --mode gradual --feature TransactionAmt
python scripts/simulate_drift.py --mode null      # control: should never alert
```

---

## 💰 Cost & Compute

Runs entirely on a student laptop — no GPU required.

| Resource | Purpose | Cost |
|---|---|---|
| Laptop (8GB+ RAM, CPU only) | Training, all detectors, full pipeline | ₹0 |
| Kaggle (free account) | IEEE-CIS dataset download | ₹0 |
| **Total** | | **₹0** |

Known compute pressure points, both addressed in Phase B:

- **MMD is O(n²)** in batch size. Subsampled to n=2000 per side; the subsample seed is fixed and recorded so results reproduce.
- **IEEE-CIS has 400+ features** and does not fit comfortably in 8GB as float64. Downcast to float32 on load, and drop columns exceeding a missingness threshold before training.

---

## 🔮 Roadmap

One constraint drives the plan: produce real, defensible numbers against a real dataset — not toy examples, not synthetic-only benchmarks. Phases run in order; each one's output is the next one's input.

### Phase 0 — Premise Validation (Day 1)
Cheapest possible check that the project's core assumption holds, before any detector is written.
- [ ] Download IEEE-CIS, load `train_transaction.csv`
- [ ] Measure actual span: `TransactionDT.max() / 86400` → confirm ~182 days
- [ ] Plot fraud rate and `TransactionAmt` distribution per 30-day bucket
- [ ] **Decision gate:** is there visible natural drift across the window?
  - Yes → Phases A–C proceed as written
  - No → Phase C engineered drift becomes the primary experiment, Phase A becomes a null result worth reporting ("IEEE-CIS shows no meaningful natural drift over 182 days")

Phase 0 exists because every downstream table assumes the model degrades. If it doesn't, better to know on day 1 than in week 3.

### Phase A — Baseline Performance Degradation
Establish how much the model degrades over the labeled window without retraining.
- [ ] `scripts/prepare_data.py` — temporal split into reference + ordered batches
- [ ] `scripts/train_model.py` — LightGBM with early stopping on a temporal validation slice
- [ ] Evaluate each batch with the frozen model
- [ ] Fill Table 1 (PR-AUC primary)
- [ ] Define the degradation threshold that Table 3 scores alerts against

### Phase B — Detectors + Alert Precision ← the core contribution
- [ ] Implement PSI, KS, MMD, ensemble behind one detector interface
- [ ] Run all detectors across all batches, label-free
- [ ] Run NannyML and Evidently on the identical batches
- [ ] Fill Table 2 (detection timing, false positives, runtime)
- [ ] Build `alert_scorer` and fill **Table 3** — alert precision vs realized degradation
- [ ] Report the ensemble result honestly, including if it beats nothing

### Phase C — Engineered Drift Scenarios
Controlled drift with known ground truth, measuring sensitivity by drift type.
- [ ] `scripts/simulate_drift.py` — gradual, sudden, prior-shift, correlation-flip, **null control**
- [ ] Run all detectors against each scenario
- [ ] Fill Table 4
- [ ] Write up which detector catches which drift type, and which it misses

### Stretch — Deployment Layer
Only after Tables 1–4 are populated. Contributes no findings; demonstrates deployment skills.
- [ ] FastAPI `/predict` + `/health`, SQLite prediction log
- [ ] Streamlit dashboard: drift score over time, alert log

### Explicitly Out of Scope

**ADWIN** reacts to error-rate changes and requires ground-truth labels. In fraud, confirmed outcomes arrive days-to-weeks after prediction, so ADWIN cannot run in the label-free setting this project is about. It is complementary to input-space methods, not a substitute — and including it would quietly undermine the premise that these detectors work without labels.

**Online retraining, multi-model adapters, streaming, GPU MMD, non-tabular data** — see [prd.md](prd.md) for the north-star versions of each.

---

## 📚 References

- [IEEE-CIS Fraud Detection Dataset](https://www.kaggle.com/competitions/ieee-fraud-detection) — Kaggle, 2019
- [Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift](https://arxiv.org/abs/1810.11953) — Rabanser et al. 2019 — closest prior work; motivates the alert-precision question
- [A Kernel Two-Sample Test](https://jmlr.org/papers/v13/gretton12a.html) — Gretton et al. 2012 — MMD theoretical basis, unbiased estimator
- [The Relationship Between Precision-Recall and ROC Curves](https://dl.acm.org/doi/10.1145/1143844.1143874) — Davis & Goadrich 2006 — why PR-AUC over ROC-AUC under class imbalance
- [Learning and Evaluating Classifiers under Sample Selection Bias](https://dl.acm.org/doi/10.1145/1015330.1015425) — Zadrozny 2004
- [Learning from Time-Changing Data with Adaptive Windowing](https://doi.org/10.1137/1.9781611972771.42) — Bifet & Gavaldà 2007 — ADWIN, discussed as out-of-scope
- [NannyML](https://github.com/NannyML/nannyml) — external comparison baseline
- [Evidently AI](https://github.com/evidentlyai/evidently) — external comparison baseline

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

*A drift alert nobody can act on is just a notification. Measure whether it predicts harm.*

</div>
