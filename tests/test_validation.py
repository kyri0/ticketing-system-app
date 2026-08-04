import pytest

from ticketing.theme import standing_label, urgency_label
from ticketing.validation import (
    ALLOWED_PRIORITIES,
    ALLOWED_STATUSES,
    ValidationError,
    required_text,
    valid_priority,
    valid_status,
)


def test_required_text_trims_value():
    assert required_text("  Sample ticket  ", "Title", max_length=255) == "Sample ticket"


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_required_text_rejects_blank_value(value):
    with pytest.raises(ValidationError, match="Title is required"):
        required_text(value, "Title")


def test_required_text_enforces_maximum_length():
    with pytest.raises(ValidationError, match="255 characters"):
        required_text("x" * 256, "Title", max_length=255)


@pytest.mark.parametrize("status", ALLOWED_STATUSES)
def test_valid_status_accepts_supported_values(status):
    assert valid_status(status) == status


def test_valid_status_rejects_unsupported_value():
    with pytest.raises(ValidationError, match="open, in_progress, resolved"):
        valid_status("closed")


@pytest.mark.parametrize("priority", ALLOWED_PRIORITIES)
def test_valid_priority_accepts_supported_values(priority):
    assert valid_priority(priority) == priority


def test_valid_priority_rejects_value_the_check_constraint_would_reject():
    with pytest.raises(ValidationError, match="low, medium, high, urgent"):
        valid_priority("catastrophic")


def test_length_error_reports_the_actual_length():
    with pytest.raises(ValidationError, match="runs to 300"):
        required_text("x" * 300, "Petition", max_length=255)


@pytest.mark.parametrize(
    "stored,shown",
    [("urgent", "Dire"), ("high", "Pressing"), ("medium", "Ordinary"), ("low", "Trifling")],
)
def test_urgency_lexicon(stored, shown):
    assert urgency_label(stored) == shown


@pytest.mark.parametrize(
    "stored,shown",
    [("open", "Open"), ("in_progress", "Underway"), ("resolved", "Settled")],
)
def test_standing_lexicon(stored, shown):
    assert standing_label(stored) == shown


def test_unknown_values_fall_back_to_the_stored_value():
    assert urgency_label("baroque") == "baroque"
    assert standing_label("closed") == "closed"



