"""drift_cause and severity classification for the drift sentinel.

Deliberately rule-based, not LLM-judged, for both fields — severity is a
lookup against a fixed money-relevant topic set, and drift_cause for
numeric fields is an exact match against git history (the only place
catalog.json's past values actually live — no snapshot table needed, git
history already gives it for free).
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A policy topic that touches money directly — anything else is "moderate."
MONEY_RELEVANT_TOPICS = {"refund", "discount"}


def classify_severity(check_type: str, ground_truth_type: str | None, ground_truth_ref: str | None) -> str | None:
    """critical | moderate | None (self_consistency rows have no ground
    truth to be critical/moderate about)."""
    if ground_truth_type == "product":
        return "critical"
    if ground_truth_type == "policy":
        _, policies = _load_ground_truth()
        policy = next((p for p in policies if p["id"] == ground_truth_ref), None)
        return "critical" if policy and policy["topic"] in MONEY_RELEVANT_TOPICS else "moderate"
    return None


def _load_ground_truth() -> tuple[list[dict], list[dict]]:
    products = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    policies = json.loads((ROOT / "policies.json").read_text(encoding="utf-8"))
    return products, policies


def _git_history_values(filename: str, item_id: str, id_field: str, value_field: str) -> list:
    """Every historical value `item_id`'s `value_field` has held in
    `filename`'s git history, oldest to newest. The only place past
    ground-truth values actually exist — no separate snapshot table."""
    log = subprocess.run(
        ["git", "log", "--format=%H", "--", filename],
        capture_output=True, text=True, cwd=ROOT,
    )
    commits = list(reversed(log.stdout.split()))

    values = []
    for commit in commits:
        show = subprocess.run(
            ["git", "show", f"{commit}:{filename}"],
            capture_output=True, text=True, cwd=ROOT,
        )
        if show.returncode != 0:
            continue
        try:
            data = json.loads(show.stdout)
        except json.JSONDecodeError:
            continue
        item = next((d for d in data if d.get(id_field) == item_id), None)
        if item is not None and value_field in item:
            values.append(item[value_field])
    return values


def classify_drift_cause(result) -> str | None:
    """stale_ground_truth | fabrication | inconsistency | None.
    None when the check wasn't flagged — nothing to classify."""
    if not result.flagged:
        return None

    if result.check_type == "self_consistency":
        return "inconsistency"

    if result.check_type == "numeric":
        history = _git_history_values("catalog.json", result.ground_truth_ref, "id", "price")
        if not history:
            return "fabrication"
        current = history[-1]
        prior = history[:-1]
        if result.actual in prior and result.actual != current:
            return "stale_ground_truth"
        return "fabrication"

    if result.check_type == "faithfulness":
        # No clean exact-match is possible here — `actual` is a full
        # natural-language response, not a discrete value comparable to a
        # past claim string the way a price is. Best-effort: a claim that
        # no longer matches ANY historical version (current or past) is
        # fabrication; one that matches an older-but-not-current version
        # is stale_ground_truth. Deliberately conservative (exact
        # substring, not semantic) — a false "fabrication" is safer to
        # over-report than a missed one, given this is a QA tool.
        history = _git_history_values("policies.json", result.ground_truth_ref, "id", "claim")
        if not history:
            return "fabrication"
        current = history[-1]
        prior = history[:-1]
        actual_text = str(result.actual)
        if any(p in actual_text for p in prior) and current not in actual_text:
            return "stale_ground_truth"
        return "fabrication"

    return None


def demo():
    assert classify_severity("numeric", "product", "prod_001") == "critical"
    assert classify_severity("faithfulness", "policy", "policy_refund_window") == "critical"  # refund topic
    assert classify_severity("faithfulness", "policy", "policy_shipping_delivery_time") == "moderate"
    assert classify_severity("self_consistency", None, None) is None

    class FakeResult:
        def __init__(self, check_type, flagged, ground_truth_ref, actual):
            self.check_type = check_type
            self.flagged = flagged
            self.ground_truth_ref = ground_truth_ref
            self.actual = actual

    assert classify_drift_cause(FakeResult("numeric", False, "prod_001", 100)) is None
    assert classify_drift_cause(FakeResult("self_consistency", True, None, "x")) == "inconsistency"
    # fabrication case: a price never in this product's real history
    assert classify_drift_cause(FakeResult("numeric", True, "prod_001", -999999)) == "fabrication"

    print("All assertions passed.")


if __name__ == "__main__":
    demo()
