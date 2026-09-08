"""Numeric-check tests need no API keys — the extraction and comparison
are pure logic. Faithfulness needs a live Groq call and is exercised by
drift/diff.py's own demo(), not here."""

from drift.diff import check_numeric


def test_matching_price_is_not_flagged():
    result = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="Rs.899")
    assert result.check_status == "completed"
    assert not result.flagged


def test_drifted_price_is_flagged():
    result = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="Rs.799")
    assert result.flagged


def test_unparseable_answer_errors_without_losing_raw_text():
    result = check_numeric("What does the beanie cost?", "prod_003", expected_price=899, actual_text="I don't know.")
    assert result.check_status == "errored"
    assert result.actual == "I don't know."


def test_price_marker_preferred_over_incidental_digits():
    # A product id or capacity mentioned before the real price must not be
    # picked up as the price — this is the bug documented in diff.py.
    result = check_numeric("How much for the bottle?", "prod_004", expected_price=749,
                            actual_text="The Stainless Steel Water Bottle 1L costs Rs.749.")
    assert not result.flagged
    assert result.actual == 749
