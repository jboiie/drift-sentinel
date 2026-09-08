# Prior Work

Drift Sentinel's detection engine isn't new. It's a standalone port of a
subsystem built for a larger project, extracted because the idea behind
it — a monitor that grades its own alerts — deserved its own repo instead
of staying buried inside a bigger one.

---

## ARGUS

The direct source. ARGUS is an agentic commerce system: an LLM support
agent with a cart, checkout via mandate-gated payment confirmation, and a
red-team harness attacking it for prompt-injection and payment-integrity
failures. Deep in that system was a "drift sentinel" subsystem — the exact
code this repo now contains — built to answer a narrower question buried
inside the bigger project: *does the support agent's answer still match
the catalog and policy data it's supposed to be grounded in?*

That subsystem was built and proven against a real, live agent. Two of
its design decisions exist specifically because a real bug was found and
fixed during that build, not because they were theorized in advance — see
[methods.md](methods.md) for both (a price-extraction regex grabbing the
wrong number, and a faithfulness score cratering when the check context
didn't cover the full multi-claim answer a broad question elicits).

**What got left behind, deliberately:** the cart, checkout, mandate
confirmation flow, Razorpay payment integration, red-team attack harness,
and Supabase telemetry. All real and load-bearing in ARGUS. None of them
relevant to whether a drift monitor's flags are worth a reviewer's time —
carrying them over would have made this repo a fork of ARGUS instead of a
standalone project about one specific, interesting idea.

**What changed in the port**, beyond deleting unused code:
- The reference agent lost its coupon/discount-blocking system-prompt
  logic, which existed only to support the cart flow
- Supabase logging became a local JSON file, matching this project's
  no-server, no-database posture
- The Groq judge model lost its DeepEval/DeepTeam base-class dependency,
  needed only for ARGUS's red-team harness

---

## Prompt-Autopsy

[github.com/jboiie/prompt-autopsy](https://github.com/jboiie/prompt-autopsy)

20 real jailbreak prompts fired at a Groq-hosted LLM, classified as
success/refusal, with per-category Attack Success Rate computed and
reported.

**What it taught:** how to design an evaluation pipeline — reference
corpus → automated scoring → aggregate metric. The same skeleton
underlies `drift/sampler.py`: a fixed set of questions, checked
automatically, rolled up into one number that matters (the false-positive
rate).

## PAIR-Lab

[github.com/jboiie/pair-lab](https://github.com/jboiie/pair-lab)

A Python implementation of the PAIR algorithm — one LLM iteratively
attacking another, scored by a judge LLM.

**What it taught:** using an LLM as a judge, with a structured schema
response, rather than parsing free text — the same pattern
`judge/groq_model.py` and RAGAS's `Faithfulness` scorer both use here.

---

## How They Connect

| Project | Core Question | Core Method |
|---|---|---|
| Prompt-Autopsy | How often do static defenses fail against a fixed attack corpus? | ASR over a labeled corpus |
| PAIR-Lab | How much worse does it get when the attacker adapts? | Iterative LLM-vs-LLM attack loop, LLM-as-judge |
| ARGUS | Can an agentic commerce system resist real attacks *and* stay factually grounded? | Red-team harness + drift sentinel, side by side |
| **Drift Sentinel** | Is a drift monitor's flag ever worth a human's time? | The drift-sentinel half of ARGUS, extracted and made to stand on its own |

The throughline: every one of these projects measures failure before a
user has to find it themselves, and none of them stop at "does it fire" —
each one goes one step further and asks whether firing means anything.
