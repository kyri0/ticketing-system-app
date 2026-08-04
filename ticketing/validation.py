"""Input validation shared by the routes and the repository.

Error messages are written to tell the scribe what to do next, not merely that
something was wrong. The stored values stay plain (`open`, `in_progress`,
`urgent`); the ledger's vocabulary lives in `ticketing.theme`.
"""

from __future__ import annotations

ALLOWED_STATUSES = ("open", "in_progress", "resolved")
ALLOWED_PRIORITIES = ("low", "medium", "high", "urgent")

MAX_TITLE = 255
MAX_NAME = 255
MAX_MESSAGE = 10_000
MAX_DESCRIPTION = 4_000


class ValidationError(ValueError):
    """Raised when user-provided input does not meet application rules."""


def required_text(value: str | None, label: str, *, max_length: int | None = None) -> str:
    """Return trimmed text, or raise a concise, user-safe validation error."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(f"{label} is required.")
    if max_length is not None and len(cleaned) > max_length:
        raise ValidationError(
            f"{label} must be {max_length} characters or fewer — "
            f"this one runs to {len(cleaned)}."
        )
    return cleaned


def valid_status(value: str) -> str:
    """Validate the only ticket status values this application supports."""
    if value not in ALLOWED_STATUSES:
        choices = ", ".join(ALLOWED_STATUSES)
        raise ValidationError(f"Status must be one of: {choices}.")
    return value


def valid_priority(value: str) -> str:
    """Validate against the CHECK constraint on tickets.priority."""
    if value not in ALLOWED_PRIORITIES:
        choices = ", ".join(ALLOWED_PRIORITIES)
        raise ValidationError(f"Priority must be one of: {choices}.")
    return value
