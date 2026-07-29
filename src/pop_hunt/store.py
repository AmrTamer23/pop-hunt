"""Persistence for detection state and the dashboard data files.

Writes are change-aware: the workflow commits these files, so rewriting an
identical file every 30 minutes would produce a commit per run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_EVENTS = 200
EMPTY_SNAPSHOT: dict[str, Any] = {"generated_at": None, "targets": []}


def _read_json(path: str | Path, default: Any) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    try:
        return json.loads(file.read_text())
    except (json.JSONDecodeError, ValueError):
        return default


def _write_json(path: str | Path, payload: Any) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_state(path: str | Path) -> dict[str, str]:
    return _read_json(path, {})


def save_state(path: str | Path, state: dict[str, str]) -> bool:
    """Write state; return True only if it changed on disk."""
    if _read_json(path, {}) == state:
        return False
    _write_json(path, state)
    return True


def load_snapshot(path: str | Path) -> dict[str, Any]:
    return _read_json(path, dict(EMPTY_SNAPSHOT))


def save_snapshot(
    path: str | Path, targets: list[dict[str, Any]], generated_at: str
) -> bool:
    """Write the dashboard feed, ignoring `generated_at` when comparing.

    Only a real content change should touch the file.
    """
    if load_snapshot(path).get("targets") == targets:
        return False
    _write_json(path, {"generated_at": generated_at, "targets": targets})
    return True


def load_events(path: str | Path) -> list[dict[str, Any]]:
    return _read_json(path, [])


def append_events(path: str | Path, new_events: list[dict[str, Any]]) -> bool:
    """Prepend new events (newest first) and cap the log. No-op if empty."""
    if not new_events:
        return False
    events = list(new_events) + load_events(path)
    _write_json(path, events[:MAX_EVENTS])
    return True
