"""Self-consistency sampler for claims not covered by ground truth.

SelfCheckGPT-style: ask the same question multiple times, disagreement
across the samples is the hallucination signal — there's no ground truth
to diff against directly (if there were, this would be a numeric or
faithfulness check instead).
"""

import asyncio
import os

from pydantic import BaseModel

from agent.reference_agent import ask_async
from drift.diff import DriftCheckResult
from judge.groq_model import GroqModel

N_SAMPLES = 3
# Below this agreement rate, the samples disagree enough to flag as a
# possible hallucination. Explicit, documented threshold (not tuned
# against a labeled set) — same posture as FAITHFULNESS_THRESHOLD.
AGREEMENT_THRESHOLD = 0.7


class ConsistencyVerdict(BaseModel):
    agreement_rate: float  # fraction of samples that agree with the majority view
    majority_answer: str  # concise summary of the consensus (or majority) answer


_JUDGE_PROMPT = """You are checking {n} answers a support agent gave to the same question, asked separately each time.

Question: {question}

Answers:
{answers}

Do the answers agree with each other in substance (not necessarily wording)? Return the fraction of the {n} answers that agree with the majority view (agreement_rate, 0.0 to 1.0), and a one-sentence summary of what the majority view actually says (majority_answer)."""


async def check_self_consistency(question: str, topic_ref: str) -> DriftCheckResult:
    """topic_ref is a short slug identifying the question (not a real
    product/policy id — there isn't one, this is specifically for claims
    ground truth doesn't cover). ground_truth_ref/ground_truth_type are
    null for self_consistency rows."""
    try:
        responses = await asyncio.gather(*[ask_async(question) for _ in range(N_SAMPLES)])
    except Exception as exc:
        print(f"  (self-consistency sampling failed for {topic_ref}: {type(exc).__name__}: {exc})")
        return DriftCheckResult(
            check_type="self_consistency", question=question, ground_truth_ref=None,
            ground_truth_type=None, expected=None, actual=None,
            score=None, check_status="errored", flagged=None,
        )

    judge = GroqModel()
    answers_block = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(responses))
    prompt = _JUDGE_PROMPT.format(n=N_SAMPLES, question=question, answers=answers_block)

    try:
        verdict: ConsistencyVerdict = await judge.a_generate(prompt, schema=ConsistencyVerdict)
    except Exception as exc:
        print(f"  (self-consistency judge failed for {topic_ref}: {type(exc).__name__}: {exc})")
        return DriftCheckResult(
            check_type="self_consistency", question=question, ground_truth_ref=None,
            ground_truth_type=None, expected=None, actual="; ".join(responses),
            score=None, check_status="errored", flagged=None,
        )

    return DriftCheckResult(
        check_type="self_consistency", question=question, ground_truth_ref=None,
        ground_truth_type=None, expected=None, actual=verdict.majority_answer,
        score=verdict.agreement_rate, check_status="completed",
        flagged=verdict.agreement_rate < AGREEMENT_THRESHOLD,
        sampled_responses=responses,
    )


async def demo():
    if not (os.environ.get("GEMINI_API_KEY") and os.environ.get("GROQ_API_KEY")):
        print("GEMINI_API_KEY/GROQ_API_KEY not set — skipping live call.")
        return

    result = await check_self_consistency("Do you offer gift wrapping?", "uncovered_gift_wrapping")
    assert result.check_status == "completed"
    assert result.sampled_responses and len(result.sampled_responses) == N_SAMPLES
    print(f"agreement_rate={result.score}, flagged={result.flagged}")
    print(f"majority_answer: {result.actual}")
    for i, r in enumerate(result.sampled_responses):
        print(f"  sample {i + 1}: {r}")


if __name__ == "__main__":
    asyncio.run(demo())
