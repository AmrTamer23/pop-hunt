"""The contract every site adapter implements."""

from __future__ import annotations

from typing import Protocol

from pop_hunt.config import Target
from pop_hunt.models import Snapshot


class SiteAdapter(Protocol):
    """Turns a rendered cinema page into a Snapshot.

    Implementations may drive the page (clicking date tabs, selecting a
    cinema) because dates are switched client-side on all three sites.
    """

    site_id: str

    def collect(self, page, target: Target) -> Snapshot:
        """Return the bookable dates and what's showing on them."""
        ...
