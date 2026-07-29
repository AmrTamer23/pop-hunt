"""The core rule: has this target's furthest bookable date advanced?"""

from __future__ import annotations

from dataclasses import dataclass

BASELINE = "baseline"
NO_CHANGE = "no_change"
NEW_DAY = "new_day"
NO_DATES = "no_dates"


@dataclass(frozen=True)
class Detection:
    status: str
    new_day_opened: bool
    previous: str | None
    new_max: str | None
    added: list[str]


def detect(previous_furthest: str | None, dates: list[str]) -> Detection:
    """Compare the furthest date seen before against this run's dates.

    ISO date strings compare chronologically as plain strings, which holds
    only for zero-padded fixed-width `YYYY-MM-DD`. Callers MUST supply dates
    in that exact form (this is what `dates.py` guarantees) — an unpadded
    date such as `2026-8-6` would sort ahead of every padded date in its
    year and permanently suppress later alerts.
    """
    if not dates:
        return Detection(NO_DATES, False, previous_furthest, None, [])

    current_max = max(dates)

    if previous_furthest is None:
        # First time we have seen this target: record silently, never alert.
        return Detection(BASELINE, False, None, current_max, [])

    if current_max > previous_furthest:
        added = sorted({d for d in dates if d > previous_furthest})
        return Detection(NEW_DAY, True, previous_furthest, current_max, added)

    return Detection(NO_CHANGE, False, previous_furthest, current_max, [])
