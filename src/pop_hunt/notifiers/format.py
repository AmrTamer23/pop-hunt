"""Build the Telegram alert text. Pure - no I/O."""

from __future__ import annotations

from html import escape

from pop_hunt.config import Target
from pop_hunt.detector import Detection


def format_alert(target: Target, detection: Detection) -> str:
    """Telegram HTML-mode message announcing a newly opened booking day."""
    added = ", ".join(detection.added)
    return (
        "🎬 <b>New booking day</b>\n\n"
        f"{escape(target.label)}\n"
        f"Now selling through <b>{detection.new_max}</b> "
        f"(was {detection.previous}).\n"
        f"New date(s): {added}\n"
        f"{escape(target.url)}"
    )
