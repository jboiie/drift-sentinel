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

## Phase 2 — Real Numbers

**Goal:** fill Tables 1 and 2 in the README with numbers from real runs,
not placeholders.

- [ ] Run `python -m drift.sampler` across enough sessions that Table 1's
  counts mean something (aim for at least 5–10 full sessions, not one)
- [ ] Manually review every flagged incident in `reports/drift_log.json`,
  setting `reviewed_at`/`is_false_positive` by hand
- [ ] Run `drift/audit.py::compute_false_positive_cost` over the reviewed
  log, fill Table 2
- [ ] Run `staged_injection.py` a second time against a policy claim (not
  just a price) — the current proof only covers the numeric check path
- [ ] Write the Key Takeaways section honestly, whatever the
  false-positive rate turns out to be

**Risk, stated plainly:** the review step is manual and by the project's
own author, which is a conflict of interest a rigorous eval wouldn't
tolerate. Mitigation: the review criterion (was this specific claim
actually wrong, checked against the ground-truth file itself) is
mechanical enough that reviewer bias has little room to operate — this
isn't a subjective quality judgment, it's confirming a price or policy
line against a JSON file.

## Phase 3 — Dashboard

**Goal:** one static page that makes the results visible without reading
a table.

- [ ] `dashboard.py` — reads `reports/drift_log.json`, writes a
  self-contained static site to `docs/`
- [ ] Incident timeline, false-positive scoreboard, drift-cause breakdown,
  staged-injection replay, run provenance — same panel-by-panel build
  order discipline as everything else in this project: ship the one panel
  that carries the argument (the false-positive scoreboard) first
- [ ] Enable GitHub Pages on `main` → `/docs`, confirm cold load under a
  second
- [ ] Static, no server, no framework — the reason Streamlit was rejected
  for the same role in this project's earlier fraud-detection design
  still applies: its free tier sleeps, and a cold spinner is the worst
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

- `pytest` passes with no API keys required
- `python -m drift.sampler` runs end-to-end against live agent + judge
- `staged_injection.py inject` → commit → `verify` → commit runs clean,
  as it already does
- Table 2's false-positive rate is a real number with a real denominator,
  not a placeholder
- Dashboard live at `jboiie.github.io/drift-sentinel`, every number on it
  generated from `reports/drift_log.json`
- README contains zero numbers that weren't produced by running the code
