# Drift Sentinel — Methods

Threshold choices, check semantics, and the classification logic, written
down so they're not just buried in code comments.

---

## 1. The Three Check Types

### Numeric

A question with a discrete, checkable answer (a price). The agent's raw
text response is parsed for a number (`drift/diff.py::_extract_number`),
preferring one immediately after a currency marker (`Rs.`/`₹`) over the
first digit sequence anywhere in the text — a naive first-number search
grabs incidental digits like a capacity ("1L"), a size ("10-inch"), or a
product id ("prod_008") mentioned before the actual price. This was a real
bug, not a hypothetical one: 3 of 8 products misparsed this way during
ARGUS's original sampler run (₹749→1, ₹1899→10, ₹599→8).

No LLM judgment involved. A price either matches the current catalog
value or it doesn't.

### Faithfulness

A question with a fuzzy, free-text answer (a policy claim). Scored with
[RAGAS Faithfulness](https://arxiv.org/abs/2309.15217): the response is
decomposed into individual claims, and each is checked against the
retrieved ground-truth context. A score of 1.0 requires every claim fully
supported.

**`FAITHFULNESS_THRESHOLD = 0.7`** — below this, flagged as drifted.
Explicit and documented, not tuned against a labeled set: tolerant of
phrasing variance, without missing an actually-wrong claim.

**Context must cover every claim under the question's topic, not just the
one being tracked.** A broad question ("what is your refund policy?")
naturally elicits an answer covering several claims. Checking that answer
against only one narrow claim's context makes RAGAS find no support for
the *other* real claims it also (correctly) mentions, and the score
craters to roughly `1/n_claims` regardless of actual correctness. This was
also a real bug: 14 of 14 faithfulness checks false-flagged this way in
ARGUS's original run, scores landing exactly on `1/n` patterns. The fix —
`drift/sampler.py` passes every claim under a topic as context when
checking any one of them — is encoded directly in the sampler, not left as
a caller's responsibility to remember.

### Self-Consistency

For questions with **no ground truth to check against at all** — nothing
in `catalog.json` or `policies.json` covers them. SelfCheckGPT-style: ask
the same question three times, and disagreement across the samples is the
hallucination signal.

**`AGREEMENT_THRESHOLD = 0.7`, `N_SAMPLES = 3`** — same posture as the
faithfulness threshold: explicit, not tuned.

**The uncovered questions must sit *adjacent* to real ground truth, not
cleanly outside it.** A plainly out-of-scope question ("do you offer gift
wrapping?") just makes the system prompt's "say you don't know"
instruction fire every time — a check that can only ever return
"consistent" isn't measuring anything. `drift/sampler.py::UNCOVERED_QUESTIONS`
picks questions that sit next to a real, adjacent fact the model can
plausibly (and inconsistently) extrapolate from: a keyboard's battery life
when a sibling product publishes a spec, a skillet's dishwasher-safety
when only oven-safety is stated. One cleanly-out-of-scope question is kept
as a contrast case, where consistent refusal is the expected and correct
result.

---

## 2. Drift Cause Classification

`drift/classify.py::classify_drift_cause` answers *why* a flagged answer
is wrong, using **git history as the ground-truth timeline** — the only
place a past value of `catalog.json`/`policies.json` actually still
exists. No snapshot table was built for this; committed JSON files already
give it for free via `git log`/`git show`.

| Check type | Classification logic |
|---|---|
| `self_consistency` | Always `inconsistency` — there's no ground truth to be stale or fabricated relative to |
| `numeric` | Exact match against every historical price this product has ever had. If the flagged value matches a *prior* (not current) price → `stale_ground_truth`. Otherwise → `fabrication` |
| `faithfulness` | Best-effort substring match against every historical claim text. No clean exact-match is possible here — `actual` is a full natural-language response, not a discrete value directly comparable to a past claim string. Deliberately conservative: a false `fabrication` is safer to over-report than a missed one, since this is a QA tool, not a legal one |

## 3. Severity

`classify_severity` is a fixed lookup, not a model call:

- Any flagged **product** (price) check → `critical`
- A flagged **policy** check → `critical` if its topic is in
  `MONEY_RELEVANT_TOPICS = {"refund", "discount"}`, else `moderate`
- A flagged **self-consistency** check → `None` (no ground truth to be
  critical or moderate *about*)

Rule-based on purpose: severity here is a fixed business judgment (money
matters more), not something that benefits from an LLM's opinion.

---

## 4. The Headline Metric — False-Positive Rate on Flags

```
false_positive_rate = false_positives / reviewed
```

computed by `drift/audit.py::compute_false_positive_cost` over logged
incidents. `reviewed` and `is_false_positive` are set by a human looking
at each flagged incident — there is no automatic ground truth for "should
this have been flagged," only for the individual numeric/faithfulness
checks themselves (which is a different, narrower question: was *this
specific claim* correct, not was flagging it *worth a reviewer's time*).

**Two things this metric can't do, stated plainly:**

- It says nothing about **missed** drift — flags that should have fired
  and didn't. There's no ground truth for what was never surfaced.
- `MISSED_DRIFT_ASSUMED_MULTIPLE = 5` in `drift/audit.py` is a stated,
  undefended assumption (a missed drift costs roughly 5x a wasted review)
  used only to justify why every threshold in this project leans toward
  over-flagging rather than under-flagging. It is not measured, and the
  module says so.

**The staged-injection experiment (`drift/staged_injection.py`) is the one
place this project has real ground truth on both sides** — a known
injected drift, checked, classified, and resynced. It's a sample size of
one, deliberately: it exists to prove the pipeline works end to end, not
to estimate a rate. The rate comes from the sampler runs in Table 2,
reviewed by hand.

---

## 5. Reproducibility

- `GEMINI_MIN_INTERVAL_SECONDS` and Groq's retry/backoff logic are both
  deterministic given the same rate-limit responses, but the model calls
  themselves are not seeded — Gemini and Groq don't expose a
  temperature-0-and-seed guarantee here. Runs are logged with a `run_id`
  and timestamp precisely because re-running is expected to produce
  different (not identical) transcripts.
- `catalog.json`/`policies.json` are the fixed, versioned ground truth.
  Every check result is reproducible **given** the transcript it was
  computed from, even though the transcript itself isn't.
