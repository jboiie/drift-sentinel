from datetime import datetime, timezone

from drift.audit import compute_false_positive_cost


def test_false_positive_cost_arithmetic():
    now = datetime.now(timezone.utc).isoformat()
    incidents = [
        {"check_type": "numeric", "flagged": False},
        {"check_type": "numeric", "flagged": True, "reviewed_at": now, "is_false_positive": False},
        {"check_type": "faithfulness", "flagged": True, "reviewed_at": now, "is_false_positive": True},
        {"check_type": "faithfulness", "flagged": True},  # pending review
    ]

    cost = compute_false_positive_cost(incidents)

    assert cost["total_flagged"] == 3
    assert cost["reviewed"] == 2
    assert cost["pending_review"] == 1
    assert cost["false_positives"] == 1
    assert cost["true_positives"] == 1
    assert cost["false_positive_rate"] == 0.5
    assert cost["review_cost"] == 2


def test_unreviewed_incidents_have_no_false_positive_rate():
    cost = compute_false_positive_cost([{"check_type": "numeric", "flagged": True}])
    assert cost["false_positive_rate"] is None
