"""Pure conversion of the date text cinemas render into ISO dates."""

from __future__ import annotations

from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_dmy(text: str) -> str:
    """'30-07-2026' -> '2026-07-30'."""
    parts = text.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"cannot parse DD-MM-YYYY from {text!r}")
    day, month, year = (int(p) for p in parts)
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_day_month(text: str, today: date) -> str:
    """'Thu 30 Jul' -> ISO, inferring the year from `today`.

    Cinemas only ever show a forward-looking window, so a month earlier than
    the current month must belong to next year (the Dec -> Jan rollover).
    """
    day: int | None = None
    month: int | None = None
    for token in text.replace(",", " ").split():
        cleaned = token.strip().lower()
        if cleaned[:3] in _MONTHS:
            month = _MONTHS[cleaned[:3]]
        elif cleaned.isdigit() and len(cleaned) <= 2 and day is None:
            day = int(cleaned)
    if day is None or month is None or not 1 <= day <= 31:
        raise ValueError(f"cannot parse day/month from {text!r}")
    year = today.year + 1 if month < today.month else today.year
    return f"{year:04d}-{month:02d}-{day:02d}"
