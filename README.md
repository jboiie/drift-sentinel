<div align="center">

# 📉 Drift Sentinel

### Catching an LLM support agent's answers drifting away from ground truth

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-in%20build-orange.svg)]()
[![Dashboard](https://img.shields.io/badge/dashboard-not%20yet%20live-lightgrey.svg)](https://jboiie.github.io/drift-sentinel/)

*A drift monitor that grades its own alerts — do they catch a real problem, or just add noise nobody reads?*

[Results](#-results) · [Dashboard](#-dashboard) · [Pipeline](#-pipeline) · [Quickstart](#-quickstart) · [Roadmap](#-roadmap)

</div>

---

> **What this is:** a customer-support agent (Gemini, answering from a product catalog and a policy list) with a watchdog sitting behind it, checking every answer against the ground truth it was supposed to use — and grading itself on whether a raised flag was ever worth a human's time.

An LLM support agent doesn't fail the way a normal service fails. It doesn't throw a 500. It answers fluently, sounds confident, and is sometimes just wrong — a price that changed since the answer was written, a policy claim invented out of thin air, or three different answers to the same question depending on the day. Nothing crashes. Nothing pages anyone. The only trace is the transcript.

Drift Sentinel watches for that. It runs three kinds of check against every answer the agent gives:

1. **Numeric drift** — does a stated price still match the catalog? Exact match, no LLM judgment needed.
2. **Faithfulness drift** — does a policy answer still say what the policy actually says? Scored with RAGAS's Faithfulness metric, which decomposes the answer into individual claims and checks each one.
3. **Self-consistency drift** — for questions with no ground truth to check against, does the agent give the same answer three times in a row? Disagreement is the hallucination signal (SelfCheckGPT-style).

Every flag gets classified — `stale_ground_truth`, `fabrication`, or `inconsistency` — using git history as the source of truth for what ground truth used to say. And every flag has a cost: a human has to look at it. **The number this project is built around is the false-positive rate on that review queue** — of the times the sentinel raised a hand, how often was it actually right?

**No results yet.** Every number below gets filled in by running the pipeline. `staged_injection.py` is the one experiment that already runs end to end — see [Results](#-results).

---

## 📌 The Problem

Most "AI agent monitoring" either isn't monitoring the thing that actually breaks, or has no way to tell you whether it's any good.

- **LLM observability tools** (LangSmith, Helicone, etc.) log latency, token cost, and traces. None of that tells you the agent quoted the wrong price.
- **Guardrail tools** check for toxicity, PII, prompt injection. None of that catches a support agent confidently stating a return window that changed last week.
- **"We eyeball the transcripts"** is what most teams actually do, and it doesn't scale past a demo.

The real failure mode in a grounded support agent is narrower and more specific: **the agent's answer stops matching the ground truth it's supposed to be grounded in.** That happens for three different reasons, and they need three different checks:

| Reason | Example | Check |
|---|---|---|
| Ground truth changed, the agent (or a cached answer) didn't catch up | Price dropped from ₹899 to ₹799, an old answer still says ₹899 | Numeric exact-match |
| The agent invents something not actually true | Claims a 90-day return window when the policy says 30 | RAGAS Faithfulness |
| The agent isn't grounded in anything, and it shows | Answers the same question three different ways | Self-consistency |

**Drift Sentinel measures whether flagging any of that is worth the human time it costs.** A monitor with a 90% false-positive rate trains its own reviewers to stop reading it — that failure mode is invisible until someone actually measures it, which is what this project does.

---

## 📊 Results

> **Status: build in progress.** The sampler (`drift/sampler.py`) needs to run across enough real sessions to populate a false-positive rate with a denominator worth reporting. What's below is what already runs and passes today.

### Staged injection — proof the sentinel actually works end to end

`drift/staged_injection.py` deliberately breaks one piece of ground truth, captures a real agent answer from before the break, and confirms the sentinel classifies it correctly *after* the break — the smallest possible end-to-end proof that isn't a unit test with mocked data.

| Step | What happens | Result |
|---|---|---|
| 1. Capture | Ask the live agent "What does the Merino Wool Beanie cost?" while the catalog still says ₹899 | Real answer captured |
| 2. Inject | Change `catalog.json`: ₹899 → ₹799. Commit it. | Ground truth now says ₹799 |
| 3. Check the stale answer | Re-check the *pre-injection* answer against the *new* ground truth | **Flagged.** `drift_cause=stale_ground_truth`, `severity=critical` |
| 4. Check a fresh answer | Ask the agent the same question again (no caching — it re-reads `catalog.json` every call) | **Not flagged.** Matches new ground truth immediately |
| 5. Resync | Revert the price, commit the revert | Git history now shows inject → catch → resync |

This is the whole argument in five steps: a monitor that can't tell "this answer used to be right" from "this answer was never right" can't actually help anyone triage. `classify_drift_cause` (`drift/classify.py`) tells those apart by walking the file's git history — the only place a past ground-truth value actually still exists.

### Table 1 — Check Coverage (per sampler run)

*Populated once `drift/sampler.py` has run enough sessions to report a real total. Product/policy counts below are fixed by `catalog.json` / `policies.json`.*

| Check Type | Ground Truth | Items Covered | Flags Raised | Notes |
|---|---|---|---|---|
| Numeric | `catalog.json` | 8 products | — | Exact match, no LLM judgment |
| Faithfulness | `policies.json` | 14 claims across 6 topics | — | RAGAS Faithfulness, threshold 0.7 |
| Self-consistency | none (uncovered questions) | 5 hand-picked questions | — | 3 samples each, agreement threshold 0.7 |

### Table 2 — The Headline: Was a Flag Worth Reading?

*The core number. Requires a review pass over logged incidents — `is_false_positive` set by a human, then `drift/audit.py::compute_false_positive_cost` does the arithmetic.*

| | Value |
|---|---|
| Total flagged | — |
| Reviewed | — |
| False positives | — |
| True positives | — |
| **False-positive rate** | — |
| Review cost (1 unit / reviewed incident) | — |

A sentinel with a high false-positive rate is a pager nobody trusts. This table is the one that says whether that's this sentinel's fate or not — and it gets reported however it comes out.

### Key Takeaways

*Populated once the sampler has run enough sessions to say something real.*

---

## 📈 Dashboard

> **Not built yet — Phase 3.** Will live at **[jboiie.github.io/drift-sentinel](https://jboiie.github.io/drift-sentinel/)**.

A static Plotly site, published to GitHub Pages, built the same way as any other static-HTML report in this project: no server, no framework, loads instantly and never sleeps (the reason Streamlit Cloud was rejected — its free tier's cold-start spinner is the worst possible first impression on a portfolio link).

| Panel | What it shows |
|---|---|
| **Incident timeline** | Every check across every sampler run, colour-coded by check type, flags marked | 
| **False-positive scoreboard** | The Table 2 numbers, oversized, next to the raw counts they're built from |
| **Drift-cause breakdown** | `stale_ground_truth` vs `fabrication` vs `inconsistency`, by severity |
| **Staged-injection replay** | The five-step table above, rendered as a before/after diff with the actual agent transcripts |
| **Run provenance** | Model versions, thresholds, git commit the check ran against |

Every number on the page comes from `reports/drift_log.json` — nothing typed into a template by hand.

---

## 🏗️ Architecture

```
   catalog.json / policies.json        session questions
   (ground truth, git-tracked)         (numeric / faithfulness / uncovered)
              │                                  │
              │                                  ▼
              │                    ┌──────────────────────────┐
              │                    │   reference_agent.ask()   │
              │                    │   Gemini, no cache,       │
              │                    │   re-reads ground truth   │
              │                    │   fresh on every call     │
              │                    └────────────┬─────────────┘
              │                                 │ answer(s)
              ▼                                 ▼
   ╔═════════════════════════════════════════════════════════╗
   ║                    DRIFT CHECKS                          ║
   ║                                                          ║
   ║  numeric ──────────► exact match vs catalog.json         ║
   ║  faithfulness ─────► RAGAS Faithfulness vs policies.json ║
   ║  self-consistency ─► 3x sample, LLM-judged agreement     ║
   ╚════════════════════════╤══════════════════════════════════╝
                            │ DriftCheckResult (flagged?)
                            ▼
              ┌──────────────────────────────┐
              │   classify.py                │
              │   drift_cause via git log:   │
              │   stale_ground_truth |       │
              │   fabrication | inconsistency│
              └────────────┬─────────────────┘
                           │
                           ▼
              reports/drift_log.json  ← committed nowhere, gitignored
                           │
                           ▼
              ╔══════════════════════════════════╗
              ║   audit.py — THE HEADLINE         ║
              ║   false-positive rate on flags,   ║
              ║   once a human reviews them        ║
              ╚══════════════════════════════════╝
```

### Design Decisions

| Decision | Rationale |
|---|---|
| **False-positive rate as the headline metric** | "The agent's answers get checked" says nothing about whether the checking is any good. "23% of flags were real" says something |
| **Numeric checks are rule-based, not LLM-judged** | A price either matches or it doesn't. An LLM call to compare two numbers adds cost and a new failure mode for zero benefit |
| **git history as the ground-truth timeline** | No snapshot table was built for past values — `catalog.json`/`policies.json` are committed files, and git already records every value they've ever held |
| **Faithfulness gets the LLM judge, numeric doesn't** | Policy text is genuinely fuzzy (phrasing varies, meaning doesn't); price is not |
| **Staged injection as the end-to-end proof** | Individual unit tests prove each function works on synthetic inputs. Staged injection proves the whole pipeline works on a real agent, a real ground-truth edit, and real git history |
| **JSON log, no database** | Same posture as the rest of this project: static files, no server, ₹0 to run |
| **Ported from a working system, not built from scratch** | The detection logic already ran against a live agent in a separate project (ARGUS) and caught real bugs during that build — see [prior_work.md](prior_work.md) |

---

## 🧰 What This Project Demonstrates

| Area | Concretely |
|---|---|
| **LLM evaluation** | RAGAS Faithfulness (claim decomposition against retrieved context), SelfCheckGPT-style consistency sampling, structured LLM-as-judge output via strict JSON schemas |
| **Systems judgement** | git history used as a ground-truth timeline instead of building a snapshot table nobody asked for |
| **Evaluation design** | A monitor that scores its own usefulness (false-positive rate on its own flags), not just whether it fires |
| **Engineering practice** | Rate-limited/retried API calls against two free-tier providers, seeded and reproducible checks, tests that need no API key or network |
| **Debugging real systems** | Two documented false-flag bugs from the source project (a price-extraction regex grabbing the wrong number, a faithfulness score cratering because the context didn't cover the full answer) fixed and encoded as regression tests, not just fixed and forgotten |
| **Scoping** | Reused a working detection engine from a larger system instead of re-deriving it, and said so — see [prior_work.md](prior_work.md) |

---

## 🚀 Pipeline

### Running a check

```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in GEMINI_API_KEY, GROQ_API_KEY (both free tier)

python -m agent.reference_agent    # smoke-test the agent alone
python -m drift.diff               # numeric + faithfulness demo
python -m drift.self_consistency   # hallucination-sampling demo
python -m drift.audit              # false-positive cost arithmetic, offline
```

### Running a full sampler session

```bash
python -m drift.sampler
# Asks one numeric question per product, one faithfulness question per
# policy topic, and 5 uncovered questions. Appends every result to
# reports/drift_log.json.
```

### The staged-injection proof

```bash
python -m drift.staged_injection inject
git add catalog.json && git commit -m "stage: inject price drift for demo"

python -m drift.staged_injection verify
git add catalog.json && git commit -m "stage: resync after drift demo"
```

---

## 📁 Project Structure

```
drift-sentinel/
│
├── agent/
│   └── reference_agent.py      # Gemini Q&A agent, grounded in catalog/policies
│
├── judge/
│   └── groq_model.py           # Groq-backed structured-output judge (free tier)
│
├── drift/
│   ├── diff.py                 # numeric exact-match + RAGAS Faithfulness
│   ├── self_consistency.py     # SelfCheckGPT-style hallucination sampling
│   ├── classify.py             # drift_cause + severity, via git history
│   ├── audit.py                # ← THE HEADLINE: false-positive cost metric
│   ├── sampler.py              # orchestrates a full check session
│   └── staged_injection.py     # end-to-end proof: inject → catch → resync
│
├── tests/                      # no API keys or network required
│
├── reports/                    # drift_log.json — gitignored, generated
├── docs/                       # Phase 3: published dashboard (GitHub Pages)
│
├── catalog.json                # ground truth: products (git history = timeline)
├── policies.json                # ground truth: policy claims
│
├── methods.md                  # threshold choices, RAGAS/self-consistency detail
├── prd.md                      # north-star vision, deliberately aspirational
├── prior_work.md               # where this code actually came from
├── resource.md                 # build plan under real constraints
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## ⚡ Quickstart

### Prerequisites

- Python 3.10+
- A free [Google AI Studio](https://aistudio.google.com/) key (`GEMINI_API_KEY`) — the agent under test
- A free [Groq](https://console.groq.com/) key (`GROQ_API_KEY`) — the judge model for faithfulness + self-consistency

### 1. Clone and install

```bash
git clone https://github.com/jboiie/drift-sentinel.git
cd drift-sentinel
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# fill in GEMINI_API_KEY and GROQ_API_KEY
```

### 3. Run the tests (no keys needed)

```bash
pytest
```

### 4. Run a live check

```bash
python -m drift.sampler
```

---

## 💰 Cost & Compute

| Resource | Purpose | Cost |
|---|---|---|
| Google AI Studio (free tier) | The agent under test | ₹0 |
| Groq (free tier) | Judge model for faithfulness + self-consistency | ₹0 |
| **Total** | | **₹0** |

Both free tiers are rate-limited per minute. `agent/reference_agent.py` and `judge/groq_model.py` both pace and retry against those limits rather than bursting and hoping — see `GEMINI_MIN_INTERVAL_SECONDS` in `.env.example`.

---

## 🔮 Roadmap

### Phase 1 — Port (done)
- [x] Port `agent/`, `judge/`, `drift/` from ARGUS, dropping cart/mandate/checkout/Supabase coupling
- [x] Adapt logging from Supabase to a local `reports/drift_log.json`
- [x] Port 13 tests, passing with no API keys required

### Phase 2 — Real Numbers
- [ ] Run `drift/sampler.py` across enough sessions for Table 1's counts to mean something
- [ ] Manual review pass over flagged incidents — set `is_false_positive` by hand
- [ ] Fill Table 2: the false-positive rate, whatever it turns out to be
- [ ] Re-run `staged_injection.py` for a second ground-truth item (a policy claim, not just a price) to widen the end-to-end proof beyond one case

### Phase 3 — Dashboard
- [ ] Static Plotly site → `docs/` → GitHub Pages
- [ ] Incident timeline, false-positive scoreboard, drift-cause breakdown, staged-injection replay
- [ ] Enable Pages on `main` → `/docs`, confirm cold load under a second

### Explicitly Out of Scope

**The cart/checkout/mandate agent, red-team attack harness, Supabase telemetry, Razorpay payment integration** — all real parts of ARGUS, none of them relevant to whether a drift monitor's flags are worth reading. Left behind on purpose, not missing by oversight. See [prior_work.md](prior_work.md).

---

## 📚 Reading That Shaped This

- [SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection](https://arxiv.org/abs/2303.08896) — Manakul et al. 2023 — the self-consistency check's basis
- [RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217) — Es et al. 2023 — the Faithfulness metric used for policy answers
- [Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift](https://arxiv.org/abs/1810.11953) — Rabanser et al. 2019 — where the "does a flag predict a real problem" framing originally came from, applied here to LLM answers instead of tabular features

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

*A drift alert nobody can act on is just a notification. Measure whether it predicts harm.*

</div>
