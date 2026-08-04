"""The ledger's vocabulary.

The database stores plain values (`open`, `in_progress`, `urgent`). Everything a
reader sees is mapped here, so the schema never has to carry the theme.

Colour now lives in `static/ledger.css`. Templates emit modifier classes such as
`urgency--urgent`, and the stylesheet decides what that looks like. Escaping is
Jinja's job — autoescape is on for every template.
"""

from __future__ import annotations

STANDING_LABELS = {"open": "Open", "in_progress": "Underway", "resolved": "Settled"}
URGENCY_LABELS = {
    "low": "Trifling",
    "medium": "Ordinary",
    "high": "Pressing",
    "urgent": "Dire",
}

# Urgency descends: the direst petitions sit at the head of the ledger.
URGENCY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}

FLASHES = {
    "entered": "Petition {n} entered in the ledger.",
    "appended": "Testimony added to petition {n}.",
    "amended": "Petition {n} amended.",
    "struck": "Petition {n} struck from the ledger.",
}


def standing_label(status: str) -> str:
    """Unknown values fall through unchanged rather than vanishing."""
    return STANDING_LABELS.get(status, status)


def urgency_label(priority: str) -> str:
    return URGENCY_LABELS.get(priority, priority)


def flash_text(code: str | None, number: str | None) -> str | None:
    """Resolve a redirect's flash code. Free text is never taken from the URL."""
    template = FLASHES.get(code or "")
    if template is None:
        return None
    return template.format(n=number or "")
