# Drift Sentinel — Build Plan

> What actually gets built, given a student schedule and ₹0 budget.

---

## Constraints

- **Budget**: ₹0. Google AI Studio + Groq free tiers only.
- **Time**: evenings, alongside coursework.
- **Starting point**: not from scratch — the detection engine (`drift/`,
  `agent/reference_agent.py`, `judge/groq_model.py`) is ported from a
  separate, already-working project (ARGUS). See [prior_work.md](prior_work.md).

---

## Why Port Instead of Build From Scratch

The original plan for this repo was a from-scratch statistical drift
pipeline over IEEE-CIS (PSI/KS/MMD on tabular fraud data, LightGBM,
alert-precision scoring). That plan is documented in git history but not
what got built.

What changed: an equivalent detection problem — does a monitor's flag
predict something a human should actually care about? — was already
solved, running against a live LLM agent, in a different project. Porting
that code is not "reusing old work to look productive." It's the same
judgment call this project has made from the start: don't rebuild what
already exists and works, spend the saved time on the part that's actually
new.

**What's actually new here, that ARGUS didn't have:**
- A standalone, minimal reference agent with the cart/checkout/mandate
  coupling stripped out — ARGUS's agent can't be dropped into another
  repo without dragging along payment and session-state machinery this
  project has no use for
- Local JSON logging in place of a Supabase dependency
- The dashboard (Phase 3) — ARGUS logs to a database queried by its own
  frontend; this project needs something that works standalone, published
  to GitHub Pages, with no backend at all

---

## Phase 1 — Port (done)

- [x] `agent/reference_agent.py` — Gemini Q&A agent, grounded in
  `catalog.json`/`policies.json`, no cart/mandate/drift_guard imports
- [x] `judge/groq_model.py` — Groq structured-output judge, DeepEval base
  class dropped
- [x] `drift/diff.py`, `drift/self_consistency.py`, `drift/classify.py`,
  `drift/audit.py` — ported with import paths adapted
- [x] `drift/sampler.py` — rewritten to log to `reports/drift_log.json`
  instead of Supabase
- [x] `drift/staged_injection.py` — ported, Supabase logging removed
- [x] 13 tests ported, passing offline (no API keys, no network)
- [x] `pyproject.toml` rewritten for the new dependency set
  (`google-genai`, `openai`, `ragas`, `langchain-community<0.4`)

## Phase 2 — Real Numbers (done)

**Goal:** fill Tables 1 and 2 in the README with numbers from real runs,
not placeholders.

- [x] Ran `python -m drift.sampler` for 5 live sessions — 135 checks
  total, 0 organic flags, 5 errored (all faithfulness, all under the
  shipping topic, across two separate sessions)
- [x] Ran `staged_injection.py` inject → commit → verify → commit, twice —
  both times caught, correctly classified `stale_ground_truth`/`critical`,
  fresh re-ask correctly left unflagged
- [x] Investigated the errored checks: reproduced the exact same shipping
  question and claims in isolation outside the sampler, got 4/4 clean.
  Rules out a code bug — the failure is on Groq's side (the judge call
  itself), most likely the empty-completion flake `judge/groq_model.py`
  already retries for but occasionally still exhausts on a free-tier key
- [x] Reported zero organic flags as the actual finding rather than
  running sessions indefinitely to manufacture one — the review-pass and
  Table 2 rate below are consequences of that finding, not unfinished work

**Manual review pass**: not run, deliberately — there is nothing flagged
to review. `drift/audit.py::compute_false_positive_cost` requires at
least one flagged incident to divide by, and 135 checks over 5 sessions
produced none. This is documented in the README as the honest result,
not worked around.

**Risk, stated plainly (now resolved):** the review step being manual and
by the project's own author was a stated conflict-of-interest risk. It
never came up in practice — there was nothing to review — but the
mitigation stands for whenever an organic flag does show up: the review
criterion (was this specific claim actually wrong, checked against the
ground-truth file itself) is mechanical enough that reviewer bias has
little room to operate.

## Phase 3 — Dashboard (done)

**Goal:** one static page that makes the results visible without reading
a table.

- [x] `drift/dashboard.py` — reads `reports/drift_log.json` and
  `reports/staged_injection_log.json`, writes a self-contained static
  site to `docs/`
- [x] Summary tiles, staged-injection replay (real transcripts), checks-
  by-type breakdown, drift-cause breakdown, run provenance — staged-
  injection replay shipped first since it's the panel that actually
  carries the argument while organic flags are still at zero
- [x] GitHub Pages enabled on `main` → `/docs`, live at
  [jboiie.github.io/drift-sentinel](https://jboiie.github.io/drift-sentinel/)
- [x] Static, no server, no framework, Plotly inlined — the reason
  Streamlit was rejected for the same role in this project's earlier
  fraud-detection design still applies: its free tier sleeps, and a cold
  spinner is the worst
  first impression a portfolio link can give

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Google AI Studio / Groq free-tier rate limits stall the sampler | High | Both `reference_agent.py` and `groq_model.py` already pace and retry against documented limits, ported from a system that hit these limits for real |
| Manual review introduces reviewer bias | Medium | Review criterion is mechanical (does this answer match the ground-truth file), not subjective |
| Faithfulness threshold (0.7) turns out miscalibrated once real data comes in | Medium | Documented as an explicit, undefended choice from the start — a Phase 2 finding that it's wrong is a legitimate result, not a bug |
| Self-consistency questions stop being "adjacent enough" once real sessions run | Low-medium | `UNCOVERED_QUESTIONS` already documents why each one was chosen; add more if all of them come back consistently refused |
| Dashboard scope creeps past a static site | Medium | Same discipline as everywhere else: read-only, computes nothing, ship the one panel that matters first |

---

## What "Done" Looks Like

- [x] `pytest` passes with no API keys required
- [x] `python -m drift.sampler` runs end-to-end against live agent + judge
- [x] `staged_injection.py inject` → commit → `verify` → commit runs clean
- [x] Dashboard live at `jboiie.github.io/drift-sentinel`, every number on
  it generated from `reports/drift_log.json` / `staged_injection_log.json`
- [x] README contains zero numbers that weren't produced by running the
  code
- [x] Table 2's false-positive rate is a real, reported result —
  `n/a`, with the reason stated: 135 checks over 5 sessions produced 0
  organic flags. Not a gap to fill later, a finding to stand behind

This build is closed. The two things genuinely left for a future session
— catching an organic flag at all, and the manual review pass that
becomes possible once one exists — aren't unfinished pieces of this plan,
they're follow-on work with no natural stopping point of their own.
