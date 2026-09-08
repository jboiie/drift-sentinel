"""No API keys or network needed — pure logic against fixture data."""

from drift.classify import classify_drift_cause, classify_severity


def test_severity_product_is_critical():
    assert classify_severity("numeric", "product", "prod_001") == "critical"


def test_severity_money_policy_is_critical():
    assert classify_severity("faithfulness", "policy", "policy_refund_window") == "critical"


def test_severity_non_money_policy_is_moderate():
    assert classify_severity("faithfulness", "policy", "policy_shipping_delivery_time") == "moderate"


def test_severity_self_consistency_has_no_severity():
    assert classify_severity("self_consistency", None, None) is None


class _FakeResult:
    def __init__(self, check_type, flagged, ground_truth_ref, actual):
        self.check_type = check_type
        self.flagged = flagged
        self.ground_truth_ref = ground_truth_ref
        self.actual = actual


def test_unflagged_result_has_no_cause():
    assert classify_drift_cause(_FakeResult("numeric", False, "prod_001", 100)) is None


def test_self_consistency_cause_is_inconsistency():
    assert classify_drift_cause(_FakeResult("self_consistency", True, None, "x")) == "inconsistency"


def test_numeric_value_never_seen_is_fabrication():
    assert classify_drift_cause(_FakeResult("numeric", True, "prod_001", -999999)) == "fabrication"
