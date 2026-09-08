# Drift Sentinel — Product Requirements Document

> **North-star vision — deliberately aspirational.** Describes what this
> becomes if fully resourced. Most of it is not being built.
>
> For what actually gets built under real constraints, see
> [resource.md](resource.md). For current status, see
> [README.md](README.md) — the only document containing measured results.

---

## Problem Statement

A team deploying an LLM agent grounded in their own data (a catalog, a
policy doc, an internal wiki) has no continuous, cheap way to know when
the agent's answers stop matching that data. The current state of the art:

1. **Nothing** — ship it, wait for a customer complaint.
2. **Spot-checking transcripts** — slow, inconsistent, doesn't scale past
   a demo.
3. **Generic LLM observability** (latency, cost, traces) — tells you the
   agent responded, not whether the response was true.

The gap: no lightweight tool continuously answers *"is this agent's
answer still grounded in what it's supposed to be grounded in, and is
that check itself worth a human's attention?"*

---

## What Drift Sentinel Becomes

A drop-in answer-drift monitor for any grounded LLM agent: point it at the
agent's Q&A interface and its ground-truth source files, and it
continuously samples questions, checks answers three ways (numeric,
faithfulness, self-consistency), classifies every flag by cause and
severity, and reports whether flagging was worth the review time it cost.

### Core User Story

> As a team running a support agent grounded in a product catalog and
> policy docs, I want to know when the agent starts giving answers that no
> longer match that ground truth — and I want to know whether my
> monitor's alerts are actually worth reading — so I can catch drift
> before a customer does, without drowning my team in false alarms.

---

## System Components (Full Vision)

### 1. Drift Checker (Core)
- Runs numeric, faithfulness, and self-consistency checks against any
  Q&A-style agent
- Configurable ground-truth sources beyond flat JSON files (a database, a
  live API, a vector store)
- Configurable thresholds per check type

### 2. Continuous Sampler
- Runs on a schedule (cron, GitHub Actions), not just on demand
- Samples real production question logs, not just a fixed hand-written set

### 3. Review Queue
- A minimal web UI for the manual `is_false_positive` review step this
  build currently does by hand against a JSON file
- Tracks reviewer agreement over time, not just a single reviewer's call

### 4. Dashboard
- Static site generated from run output: incident timeline,
  false-positive scoreboard, drift-cause breakdown
- Published to GitHub Pages off `main` → `/docs` (free, no cold start)

### 5. Multi-Agent Support
- Currently assumes one Gemini agent grounded in two flat JSON files
- Full vision: any agent framework, any ground-truth source, adapter
  pattern per source type

---

## North-Star Extensions (Out of Scope for This Iteration)

### Automatic Ground-Truth Diffing at Scale
Currently, `classify_drift_cause`'s git-history lookup works because there
are exactly two small, git-tracked JSON files. A production ground-truth
source (a live database) needs a real snapshot/versioning strategy, not
"read git log."

### Alerting Integration
Slack/PagerDuty hooks on flagged incidents above a severity threshold.
Not built — this project's output is a static report, not a live paging
system.

### Cross-Agent Comparison
Run the same check suite against two different agent configurations
(different prompts, different models) and compare false-positive rates
directly. Would turn this from a monitor into an eval harness for prompt
changes.

---

## Success Metrics

| Metric | Target |
|---|---|
| **False-positive rate on flagged incidents** | Measured and reported, whatever it turns out to be — no target set in advance, since gaming a pre-set target here would mean tuning thresholds to flatter the number instead of catching real drift |
| Staged-injection detection | 100% — a known, injected ground-truth change must always be caught and correctly classified. This is the one metric with an actual target, because it's the one thing with unambiguous ground truth |
| Setup time | New user running `pytest` (no API keys) in under 10 minutes from clone |
| Compute cost | Full sampler session (8 products + 6 policy topics + 5 uncovered questions) completes within free-tier rate limits |

---

## Out of Scope (This Iteration)

- Multi-agent / multi-framework support (Gemini only, one agent)
- Ground-truth sources beyond flat JSON files
- Scheduled/continuous sampling (manual invocation only)
- A review-queue UI (manual JSON editing for now)
- Alerting integrations (Slack, PagerDuty, email)
