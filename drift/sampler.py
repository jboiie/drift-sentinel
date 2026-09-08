"""Sampler that simulates repeated sessions asking overlapping questions
against the reference agent.

Ties together all three check types:
- One numeric question per product (exact-match against catalog.json).
- One faithfulness question per policy topic, evaluated once per claim
  under that topic (each claim keeps its own policy id for a real,
  traceable ground_truth_ref, rather than inventing a topic-level id).
- A handful of hand-picked questions with no ground-truth basis at all
  (self-consistency).

Meant to be run repeatedly over time, not once, so the drift-over-time
chart is a real timeline rather than one synthetic batch. Results are
written to reports/drift_log.json — no database, same "static file, no
server" posture as the rest of this project.
"""

import asyncio
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from agent.reference_agent import ask_async, load_ground_truth
from drift.classify import classify_drift_cause, classify_severity
from drift.diff import DriftCheckResult, check_faithfulness, check_numeric
from drift.self_consistency import check_self_consistency

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "reports" / "drift_log.json"

# Questions with no basis in catalog.json/policies.json.
#
# These are deliberately ADJACENT to real ground truth rather than cleanly
# outside it, and that distinction is the whole point of the check. A
# question that's plainly out of scope ("do you offer gift wrapping?")
# just makes the system prompt's "say you don't know" instruction fire
# every time — a check that can only ever return "consistent" isn't
# measuring anything.
#
# Self-consistency detects hallucination when the model DOES answer and
# invents details that vary between samples. That needs a question sitting
# next to real data, where there's something to extrapolate from:
# prod_006 publishes "12-hour battery life" while prod_001 is Bluetooth
# with no battery spec at all; the warranty policy covers electronics but
# says nothing about accessories; the beanie is "machine washable" while no
# other product states care instructions. Those gaps are where a model
# fills in plausibly and inconsistently.
UNCOVERED_QUESTIONS = [
    ("How long does the Wireless Mechanical Keyboard last on a single charge?", "uncovered_keyboard_battery"),
    ("What type of switches does the Wireless Mechanical Keyboard use?", "uncovered_keyboard_switch_type"),
    ("Is the Cast Iron Skillet dishwasher safe?", "uncovered_skillet_dishwasher"),
    ("What warranty comes with the Leather Bifold Wallet?", "uncovered_wallet_warranty"),
    # Contrast case: cleanly outside ground truth, so a consistent refusal
    # here is the expected and correct result.
    ("Do you offer gift wrapping?", "uncovered_gift_wrapping"),
]


def _numeric_question(product: dict) -> str:
    return f"What does the {product['name']} cost?"


def _faithfulness_question(topic: str) -> str:
    return f"What is your {topic} policy?"


async def run_session() -> list[tuple[DriftCheckResult, list[str]]]:
    """Returns each result paired with the RAW agent text(s) that produced
    it — not r.actual, which for a numeric check is the parsed number, not
    what the agent actually said."""
    products, policies = load_ground_truth()
    results: list[tuple[DriftCheckResult, list[str]]] = []

    for product in products:
        question = _numeric_question(product)
        answer = await ask_async(question)
        results.append((check_numeric(question, product["id"], product["price"], answer), [answer]))

    topics: dict[str, list[dict]] = {}
    for policy in policies:
        topics.setdefault(policy["topic"], []).append(policy)

    for topic, claims in topics.items():
        question = _faithfulness_question(topic)
        answer = await ask_async(question)
        # One faithfulness row per claim under the topic, but ALL claims
        # under the topic go in as context — a topic question naturally
        # elicits a multi-claim answer, and checking that against only one
        # narrow claim's context false-flags the other real claims it also
        # (correctly) mentions.
        context = [c["claim"] for c in claims]
        for claim in claims:
            result = await check_faithfulness(question, claim["id"], claim["claim"], answer, context_claims=context)
            results.append((result, [answer]))

    for question, ref in UNCOVERED_QUESTIONS:
        result = await check_self_consistency(question, ref)
        results.append((result, result.sampled_responses or []))

    return results


def _to_incident(result: DriftCheckResult, run_id: str, session_id: str) -> dict:
    incident = asdict(result)
    incident["run_id"] = run_id
    incident["session_id"] = session_id
    incident["incident_id"] = str(uuid.uuid4())
    incident["logged_at"] = datetime.now(timezone.utc).isoformat()
    incident["drift_cause"] = classify_drift_cause(result)
    incident["severity"] = classify_severity(result.check_type, result.ground_truth_type, result.ground_truth_ref)
    return incident


def _append_log(incidents: list[dict]) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    existing = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else []
    existing.extend(incidents)
    LOG_PATH.write_text(json.dumps(existing, indent=2, default=str) + "\n", encoding="utf-8")


async def run_and_log(run_id: str) -> list[DriftCheckResult]:
    session_id = str(uuid.uuid4())
    pairs = await run_session()
    incidents = [_to_incident(r, run_id, session_id) for r, _ in pairs]
    _append_log(incidents)
    return [r for r, _ in pairs]


def _summarize(results: list[DriftCheckResult]) -> None:
    print(f"\n{len(results)} checks run:")
    for r in results:
        status = "FLAGGED" if r.flagged else ("errored" if r.check_status == "errored" else "ok")
        print(f"  [{status}] {r.check_type} / {r.ground_truth_ref or '(uncovered)'} - {r.question}")
        if r.flagged:
            print(f"      expected={r.expected!r} actual={r.actual!r} score={r.score}")


def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set — skipping live run.")
        return

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    results = asyncio.run(run_and_log(run_id))
    _summarize(results)
    print(f"\nAppended {len(results)} rows to {LOG_PATH} under run_id={run_id}")


if __name__ == "__main__":
    main()
