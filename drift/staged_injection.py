"""Deliberately inject one ground-truth change, confirm the sentinel
catches it and classifies it correctly. The end-to-end proof that this
project's core claim actually holds, not just each piece in isolation.

The reference agent re-reads catalog.json fresh on every single call (no
caching — see agent/reference_agent.py::load_ground_truth) so it can
never itself go stale mid-session: a live re-ask immediately after any
ground-truth edit reflects the new value right away. Real staleness only
ever comes from a PAST answer (logged, cached, replayed) surfacing after
ground truth has moved on — so that's exactly what this script
demonstrates: capture a real answer before the edit, inject the edit,
then show the sentinel correctly classifies the pre-edit answer as
stale_ground_truth (not fabrication) once checked against the new
ground truth, while a fresh re-ask after the edit is NOT flagged at all.

Two phases, run as two separate invocations (`inject` then `verify`) with
a real `git commit` of the catalog.json edit in between — drift_cause's
git-history classification needs that edit actually committed to work.
State handed off via a small local JSON file, not module state, since
each phase is its own process.

    python -m drift.staged_injection inject
    git add catalog.json && git commit -m "..."
    python -m drift.staged_injection verify
    git add catalog.json && git commit -m "..."  # the resync
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from agent.reference_agent import ask_async
from drift.classify import classify_drift_cause, classify_severity
from drift.diff import check_numeric

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog.json"
STATE_PATH = ROOT / ".drift_injection_state.json"  # gitignored scratch, not committed
PRODUCT_ID = "prod_003"  # Merino Wool Beanie
NEW_PRICE = 799  # from 899


def _set_price(product_id: str, price: int) -> None:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for product in data:
        if product["id"] == product_id:
            product["price"] = price
            break
    CATALOG_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


async def inject():
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    original_price = next(p["price"] for p in data if p["id"] == PRODUCT_ID)
    question = "What does the Merino Wool Beanie cost?"

    print(f"Ground truth before injection: {PRODUCT_ID} = {original_price}")
    stale_answer = await ask_async(question)
    print(f"Agent's answer (captured now, will become stale): {stale_answer!r}")

    _set_price(PRODUCT_ID, NEW_PRICE)
    STATE_PATH.write_text(json.dumps({
        "original_price": original_price, "question": question, "stale_answer": stale_answer,
    }))
    print(f"\nInjected: {PRODUCT_ID} {original_price} -> {NEW_PRICE} in catalog.json")
    print("Now commit this file before running `verify` - drift_cause needs it in git history.")


async def verify():
    state = json.loads(STATE_PATH.read_text())
    original_price, question, stale_answer = state["original_price"], state["question"], state["stale_answer"]

    print("Re-asking after injection (agent has no cache - should reflect new price immediately)")
    fresh_answer = await ask_async(question)
    print(f"Agent's answer (fresh, post-injection): {fresh_answer!r}")

    print("\nChecking the STALE (pre-injection) answer against the NEW ground truth:")
    stale_result = check_numeric(question, PRODUCT_ID, NEW_PRICE, stale_answer)
    stale_cause = classify_drift_cause(stale_result)
    stale_severity = classify_severity(stale_result.check_type, stale_result.ground_truth_type, stale_result.ground_truth_ref)
    print(f"  flagged={stale_result.flagged}, expected={stale_result.expected}, actual={stale_result.actual}")
    print(f"  drift_cause={stale_cause}, severity={stale_severity}")
    assert stale_result.flagged, "expected the stale answer to be flagged"
    assert stale_cause == "stale_ground_truth", f"expected stale_ground_truth, got {stale_cause}"
    assert stale_severity == "critical", f"expected critical (product price), got {stale_severity}"

    print("\nChecking the FRESH (post-injection) answer against the NEW ground truth:")
    fresh_result = check_numeric(question, PRODUCT_ID, NEW_PRICE, fresh_answer)
    print(f"  flagged={fresh_result.flagged}, expected={fresh_result.expected}, actual={fresh_result.actual}")
    assert not fresh_result.flagged, "expected the fresh post-injection answer to NOT be flagged"

    print(f"\nReverting catalog.json: {PRODUCT_ID} {NEW_PRICE} -> {original_price} (resync)")
    _set_price(PRODUCT_ID, original_price)
    STATE_PATH.unlink(missing_ok=True)
    print("Now commit this revert - git history should show inject -> catch -> resync.")
    print("\nAll assertions passed - drift correctly caught, classified, and logged.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("inject", "verify"):
        print("Usage: python -m drift.staged_injection [inject|verify]")
        sys.exit(1)
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set - skipping live run.")
        sys.exit(0)
    asyncio.run(inject() if sys.argv[1] == "inject" else verify())
