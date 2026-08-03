# Prior Work

Drift Sentinel is the third project in a series focused on ML evaluation methodology.

---

## Prompt-Autopsy

[github.com/jboiie/prompt-autopsy](https://github.com/jboiie/prompt-autopsy)

The first project. 20 real jailbreak prompts fired at a Groq-hosted LLM, classified as success/refusal using heuristic regex patterns, with per-category Attack Success Rate (ASR) computed and reported.

**What it taught:** how to design an evaluation pipeline — reference set of inputs, automated classification of outputs, aggregate metric over a corpus. The same structure (reference corpus → automated scoring → aggregate metric) is the skeleton of Drift Sentinel's monitoring pipeline.

---

## PAIR-Lab

[github.com/jboiie/pair-lab](https://github.com/jboiie/pair-lab)

The second project. A faithful Python implementation of the PAIR algorithm (Chao et al. 2023) — one LLM iteratively attacking another, scored by a judge LLM, with ASR and iterations-to-success tracked.

**What it taught:** that adaptive adversaries (LLMs that update their attack based on feedback) break static defenses far more effectively than fixed-corpus attacks. A LightGBM fraud classifier faces the same dynamic: fraud patterns adapt to detection, which is exactly why a static trained model degrades over time. The "attacker adapts to defender" problem in LLM security and the "distribution shifts over time" problem in production ML are structurally the same problem.

---

## How They Connect

The three projects form a coherent arc:

| Project | Core Question | Core Method |
|---|---|---|
| Prompt-Autopsy | How often do static defenses fail against a fixed attack corpus? | ASR measurement over a labeled corpus |
| PAIR-Lab | How much worse does it get when the attacker adapts? | Iterative LLM-vs-LLM attack loop |
| Drift Sentinel | Do the standard failure detectors actually predict failure? | Label-free drift detection, alerts graded against withheld labels |

All three are fundamentally evaluation problems: how do you measure failure *before* it becomes visible to users, and how do you make those measurements externally comparable rather than self-referential?

The progression is in what gets measured. Prompt-Autopsy measured a system's failure rate. PAIR-Lab measured how that rate moves under an adaptive adversary. Drift Sentinel turns the instrument on itself — measuring not whether the model fails, but whether the thing that is supposed to warn you about failure is any good at it. Each project moves one level up: system, then attacker, then monitor.
