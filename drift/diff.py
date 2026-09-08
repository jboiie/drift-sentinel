"""Ground-truth diffing: exact-match for numeric fields, RAGAS Faithfulness
for policy text.

Numeric fields are deliberately rule-based, not an LLM call — a price is a
number in the response or it isn't, and asking a second LLM to compare two
numbers adds cost and a new failure mode for zero benefit. RAGAS is
reserved for the genuinely fuzzy case: does a free-text policy answer
match a free-text ground-truth claim.
"""

import os
import re
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness

from judge.groq_model import DEFAULT_MODEL, GROQ_BASE_URL

# Below this Faithfulness score, a response is flagged as drifted. RAGAS
# decomposes a response into individual claims and checks each against the
# ground-truth context — 1.0 requires every claim fully supported. 0.7 is
# an explicit, documented threshold (not tuned against a labeled set):
# tolerates minor phrasing variance without missing an actually-wrong claim.
FAITHFULNESS_THRESHOLD = 0.7


def _judge_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=GROQ_BASE_URL)


@dataclass
class DriftCheckResult:
    check_type: str  # "numeric" | "faithfulness" | "self_consistency"
    question: str
    ground_truth_ref: str | None  # null for self_consistency — no product/policy id applies
    ground_truth_type: str | None  # "product" | "policy" | null for self_consistency
    expected: Any  # snapshot at check-time. null for self_consistency
    actual: Any
    score: float | None
    check_status: str  # "completed" | "errored"
    flagged: bool | None  # null when check_status = errored, not false
    sampled_responses: list[str] | None = None  # self_consistency rows only


_PRICE_RE = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _extract_number(text: str) -> float | None:
    """Prefer a number immediately after Rs./₹ (the price marker the
    system prompt always uses, e.g. "Rs.899") over the first number
    anywhere in the text — a naive first-number-anywhere search grabs
    incidental digits that appear earlier, like a capacity ("1L"), a size
    ("10-inch"), or a product id ("prod_008") mentioned before the actual
    price."""
    match = _PRICE_RE.search(text)
    if match:
        raw = match.group(1)
    else:
        fallback = _NUMBER_RE.search(text)
        raw = fallback.group() if fallback else None
    return float(raw.replace(",", "")) if raw else None


def check_numeric(question: str, product_id: str, expected_price: float, actual_text: str) -> DriftCheckResult:
    """Exact match against a number pulled from the agent's raw text
    response. A parse failure stores the raw text itself (useful for
    debugging why it failed) rather than null — check_status=errored is
    what signals the failure, not an absent actual."""
    actual_price = _extract_number(actual_text)
    if actual_price is None:
        return DriftCheckResult(
            check_type="numeric", question=question, ground_truth_ref=product_id,
            ground_truth_type="product", expected=expected_price, actual=actual_text,
            score=None, check_status="errored", flagged=None,
        )
    return DriftCheckResult(
        check_type="numeric", question=question, ground_truth_ref=product_id,
        ground_truth_type="product", expected=expected_price, actual=actual_price,
        score=None, check_status="completed", flagged=actual_price != expected_price,
    )


async def check_faithfulness(question: str, policy_id: str, claim: str, response: str, context_claims: list[str] | None = None) -> DriftCheckResult:
    """RAGAS Faithfulness: decomposes `response` into claims, checks each
    against retrieved context. context_claims defaults to [claim] alone,
    but a caller asking one broad question that naturally covers several
    claims (e.g. "what is your refund policy?") MUST pass every claim
    under that topic, not just the one being tracked — otherwise RAGAS
    finds no support for the OTHER real claims in the response (since
    they're true but outside the narrow context given) and the score
    craters to roughly 1/n_claims regardless of actual correctness.
    `claim` (the specific tracked claim) still becomes `expected`."""
    contexts = context_claims if context_claims else [claim]
    try:
        scorer = Faithfulness(llm=llm_factory(DEFAULT_MODEL, client=_judge_client()))
        result = await scorer.ascore(user_input=question, response=response, retrieved_contexts=contexts)
        score = result.value
    except Exception as exc:
        # Print the cause rather than swallowing it — a silent `errored`
        # row tells you a check failed but not why.
        print(f"  (faithfulness check errored for {policy_id}: {type(exc).__name__}: {exc})")
        return DriftCheckResult(
            check_type="faithfulness", question=question, ground_truth_ref=policy_id,
            ground_truth_type="policy", expected=claim, actual=response,
            score=None, check_status="errored", flagged=None,
        )
    return DriftCheckResult(
        check_type="faithfulness", question=question, ground_truth_ref=policy_id,
        ground_truth_type="policy", expected=claim, actual=response,
        score=score, check_status="completed", flagged=score < FAITHFULNESS_THRESHOLD,
    )


async def demo():
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set — skipping live call.")
        return

    numeric_ok = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="Rs.899")
    numeric_drift = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="Rs.799")
    numeric_unparseable = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="I don't know.")
    assert not numeric_ok.flagged and numeric_ok.check_status == "completed"
    assert numeric_drift.flagged
    assert numeric_unparseable.check_status == "errored" and numeric_unparseable.actual == "I don't know."
    print(f"numeric (matching): flagged={numeric_ok.flagged}")
    print(f"numeric (drifted): flagged={numeric_drift.flagged}, expected={numeric_drift.expected}, actual={numeric_drift.actual}")
    print(f"numeric (unparseable): check_status={numeric_unparseable.check_status}, actual={numeric_unparseable.actual!r}")

    claim = "Items can be returned for a refund within 30 days of delivery."
    faithful = await check_faithfulness("What is the refund window?", "policy_refund_window", claim,
                                         "Items can be returned for a refund within 30 days of delivery.")
    unfaithful = await check_faithfulness("What is the refund window?", "policy_refund_window", claim,
                                           "Items can be returned for a refund within 90 days, no questions asked.")
    assert faithful.check_status == "completed" and not faithful.flagged
    assert unfaithful.check_status == "completed" and unfaithful.flagged
    print(f"faithfulness (matching): score={faithful.score}, flagged={faithful.flagged}")
    print(f"faithfulness (drifted): score={unfaithful.score}, flagged={unfaithful.flagged}")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(demo())
