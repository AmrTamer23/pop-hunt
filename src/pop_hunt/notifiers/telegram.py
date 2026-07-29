"""Send alerts via the Telegram Bot API. Best-effort: never raises."""

from __future__ import annotations

import logging

import requests

from pop_hunt.config import Settings

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT_SECONDS = 15


def send(settings: Settings, text: str) -> bool:
    """Return True if Telegram accepted the message.

    A missing config or any failure is logged and returns False, so a broken
    notifier can never abort the monitoring run.
    """
    if not settings.telegram_enabled:
        log.warning("Telegram is not configured; skipping alert:\n%s", text)
        return False

    try:
        response = requests.post(
            API_URL.format(token=settings.telegram_bot_token),
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except Exception:
        log.exception("Telegram send failed")
        return False
