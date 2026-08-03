# Drift Sentinel — Product Requirements Document

> **North-star vision — deliberately aspirational.** Describes what this becomes if fully resourced. Most of it is not being built.
>
> For what actually gets built under real constraints, see [resource.md](resource.md). For current status, see [README.md](README.md) — which is the only document containing measured results.

---

## Problem Statement

Production ML teams have no continuous, standardized way to measure model degradation before it affects users. The current state of the art is:

1. **Scheduled retraining** — retrain every N days regardless of drift. Misses fast drift, wastes compute on stable periods.
2. **Manual metric review** — someone checks a dashboard periodically. Slow, inconsistent, doesn't scale.
3. **User complaints** — the model has already failed publicly before anyone notices.

The gap: no tool continuously answers *"is my model's input distribution shifting right now, and by how much?"* in a way that's cheap enough to run continuously, early enough to act on, and rigorous enough to trust.

---

## What Drift Sentinel Becomes

A drop-in monitoring sidecar: deploy it alongside any sklearn-compatible model, point it at your prediction log, and it produces continuous drift scores with configurable alerting thresholds. Zero changes to the model or serving infrastructure required.

### Core User Story

> As an ML engineer at a company with a deployed fraud classifier, I want to know when incoming transaction data starts differing significantly from my training distribution — before my model's accuracy visibly degrades — so I can trigger retraining proactively rather than reactively.

---

## System Components (Full Vision)

### 1. Drift Monitor (Core)
- Consumes a reference dataset (training distribution) and a stream of incoming prediction batches
- Runs PSI, KS, MMD, and ensemble detection on each batch
- Outputs a drift score per batch, flagged features, and an ensemble verdict
- Configurable thresholds: `--fail-above 0.20` for PSI, `--mmd-threshold 0.05`, etc.

### 2. Model Server (Reference Target)
- FastAPI wrapper around a serialized sklearn/LightGBM model
- Logs every prediction: input features, output probability, timestamp
- Exposes `/predict`, `/health`, `/metrics` endpoints
- Prediction log queryable by the monitor pipeline

### 3. Report Generator
- Static HTML report: drift scores over time, flagged features, performance delta
- JSON summary for CI integration
- Exit code 1 if drift exceeds threshold (enables CI pipeline gating)

### 4. Dashboard
- Streamlit: rolling drift score chart, feature distribution overlays, alert history
- Optionally deployable to Streamlit Cloud (free tier)

### 5. Drift Simulator (Research)
- Injects controlled drift scenarios for benchmarking detector sensitivity
- Four modes: gradual feature shift, sudden concept drift, prior probability drift, covariate shift
- Used to populate Table 3 (Phase C findings)

---

## North-Star Extensions (Out of Scope for This Iteration)

### ADWIN (Adaptive Windowing)
- Concept drift detection using a sliding window on model error rate
- Requires ground-truth labels (delayed feedback) — not always available
- Complements input-space methods (PSI/KS/MMD) with output-space monitoring

### Online Retraining Loop
- Monitor detects drift → triggers automated retraining on recent window → deploys updated model → monitor resets reference distribution
- Closes the loop: monitoring becomes self-healing

### Multi-Model Support
- Currently assumes one LightGBM model
- Full vision: adapter pattern for any sklearn-compatible model, HuggingFace transformer, or custom API endpoint

### Label Feedback Integration
- When ground-truth labels arrive (e.g., confirmed fraud cases after investigation), backfill performance metrics and calibrate detector thresholds against realized drift impact

---

## Success Metrics

| Metric | Target |
|---|---|
| **Alert precision** | > 50% of alerts precede real performance degradation — i.e. the alert is worth reading |
| **Alert recall** | > 80% of degradation events preceded by an alert |
| Early detection lead time | Drift flagged at least one full batch before PR-AUC crosses the degradation threshold |
| False positive rate | < 10% on the null-control stream (no injected drift) |
| Compute cost | Full batch scan (n=5000) in < 10 seconds on CPU |
| Setup time | New user running first drift check in < 15 minutes from clone |

Alert precision and recall are the primary targets. A detector with perfect recall and 5% precision is a pager that cries wolf nineteen times out of twenty — technically sensitive, operationally useless. Targets are aspirational; the measured values go in README Table 3 whatever they turn out to be.

---

## Out of Scope (This Iteration)

- GPU-accelerated MMD (not needed at student-budget scale)
- Kubernetes deployment (Docker Compose sufficient for demo)
- Real-time streaming (batch-based monitoring covers the research questions)
- Support for non-tabular data (images, text) — tabular fraud data only
