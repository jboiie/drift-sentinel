"""Audit trail + false-positive cost metric for the drift sentinel.

Cost model is deliberately simple and explicit, not tuned or
sophisticated — it only needs to exist and be honest.
"""

from datetime import datetime, timezone

REVIEW_COST = 1  # cost of a human reviewing one flagged incident

# Explicit, stated assumption: a real drift that reaches a user
# undetected is worse than the cost of one wasted review — not something
# this metric can actually count (there's no ground truth on what SHOULD
# have been flagged but wasn't), but it's the reasoning behind why
# FAITHFULNESS_THRESHOLD (drift/diff.py) and AGREEMENT_THRESHOLD
# (drift/self_consistency.py) both lean toward over-flagging rather than
# under-flagging: a false alarm costs one review; a missed drift is
# assumed to cost several times that in downstream damage.
MISSED_DRIFT_ASSUMED_MULTIPLE = 5


def compute_false_positive_cost(incidents: list[dict]) -> dict:
    """incidents: drift_incidents rows as loaded from reports/drift_log.json
    (plain dicts, not DriftCheckResult — this operates on logged history,
    not a single run). Only flagged rows carry any review cost — an
    unflagged row was never surfaced for review at all."""
    flagged = [i for i in incidents if i.get("flagged")]
    reviewed = [i for i in flagged if i.get("reviewed_at")]
    pending = [i for i in flagged if not i.get("reviewed_at")]
    false_positives = [i for i in reviewed if i.get("is_false_positive")]
    true_positives = [i for i in reviewed if i.get("is_false_positive") is False]

    return {
        "total_flagged": len(flagged),
        "reviewed": len(reviewed),
        "pending_review": len(pending),
        "false_positives": len(false_positives),
        "true_positives": len(true_positives),
        "false_positive_rate": (len(false_positives) / len(reviewed)) if reviewed else None,
        "review_cost": len(reviewed) * REVIEW_COST,
    }


def print_audit_trail(incidents: list[dict]) -> None:
    """Full per-incident detail — question, expected/actual, score,
    classification, review status."""
    for i in incidents:
        status = "FLAGGED" if i.get("flagged") else ("errored" if i.get("check_status") == "errored" else "ok")
        review = "unreviewed"
        if i.get("reviewed_at"):
            review = "false positive" if i.get("is_false_positive") else "confirmed"
        print(f"[{status}] {i['check_type']} / {i.get('ground_truth_ref') or '(uncovered)'} - {i['question']}")
        print(f"    expected={i.get('expected')!r} actual={i.get('actual')!r} score={i.get('score')}")
        if i.get("flagged"):
            print(f"    drift_cause={i.get('drift_cause')} severity={i.get('severity')} review={review}")


def demo():
    now = datetime.now(timezone.utc).isoformat()
    incidents = [
        {"check_type": "numeric", "ground_truth_ref": "prod_001", "question": "q1", "expected": 100, "actual": 100, "score": None, "check_status": "completed", "flagged": False},
        {"check_type": "numeric", "ground_truth_ref": "prod_002", "question": "q2", "expected": 100, "actual": 90, "score": None, "check_status": "completed", "flagged": True, "drift_cause": "fabrication", "severity": "critical", "reviewed_at": now, "is_false_positive": False},
        {"check_type": "faithfulness", "ground_truth_ref": "policy_x", "question": "q3", "expected": "claim", "actual": "response", "score": 0.4, "check_status": "completed", "flagged": True, "drift_cause": "fabrication", "severity": "moderate", "reviewed_at": now, "is_false_positive": True},
        {"check_type": "faithfulness", "ground_truth_ref": "policy_y", "question": "q4", "expected": "claim2", "actual": "response2", "score": 0.5, "check_status": "completed", "flagged": True, "drift_cause": "fabrication", "severity": "moderate"},  # pending review
    ]

    cost = compute_false_positive_cost(incidents)
    assert cost["total_flagged"] == 3
    assert cost["reviewed"] == 2
    assert cost["pending_review"] == 1
    assert cost["false_positives"] == 1
    assert cost["true_positives"] == 1
    assert cost["false_positive_rate"] == 0.5
    assert cost["review_cost"] == 2

    print_audit_trail(incidents)
    print("\ncost metric:", cost)
    print("\nAll assertions passed.")


if __name__ == "__main__":
    demo()
