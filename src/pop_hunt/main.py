"""One monitoring run: render every target, detect, alert, persist."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pop_hunt.adapters import get_adapter
from pop_hunt.config import Settings, Target, load_settings, load_targets
from pop_hunt.detector import NEW_DAY, NO_DATES, Detection, detect
from pop_hunt.fetcher import browser_session, collect_target
from pop_hunt.models import Snapshot
from pop_hunt.notifiers import telegram
from pop_hunt.notifiers.format import format_alert
from pop_hunt.store import (
    append_events,
    load_snapshot,
    load_state,
    save_snapshot,
    save_state,
)

log = logging.getLogger(__name__)

TARGETS_FILE = "targets.yaml"
STATE_FILE = "state.json"
SNAPSHOT_FILE = "data/snapshot.json"
EVENTS_FILE = "data/events.json"


def build_entry(target: Target, snapshot: Snapshot, status: str) -> dict[str, Any]:
    """The dashboard's view of one target."""
    return {
        "id": target.id,
        "label": target.label,
        "url": target.url,
        "site": target.site,
        "scope": target.scope,
        "dates": list(snapshot.dates),
        "movies": [movie.to_dict() for movie in snapshot.movies],
        "status": status,
    }


def carry_over(target: Target, previous: dict[str, Any], now: str) -> dict[str, Any]:
    """Reuse the last good entry so a failed render doesn't empty the dashboard.

    `stale_since` is stamped once per outage and then preserved, including for
    a target that has never rendered. Re-stamping it every run would make
    snapshot.json differ every run, and the workflow commits that file - a
    commit every 30 minutes for a target that is merely still down.
    """
    prior = next(
        (e for e in previous.get("targets") or [] if e.get("id") == target.id), None
    )

    # Shallow copy: nothing here mutates the nested lists, so it stays cheap
    # while leaving `previous` untouched.
    if prior is not None and prior.get("movies"):
        carried = dict(prior)
        carried["status"] = "stale"
        carried.setdefault("stale_since", now)
        return carried

    return {
        "id": target.id,
        "label": target.label,
        "url": target.url,
        "site": target.site,
        "scope": target.scope,
        "dates": [],
        "movies": [],
        "status": "error",
        "stale_since": (prior or {}).get("stale_since") or now,
    }


def run_targets(
    targets: list[Target],
    state: dict[str, str],
    previous: dict[str, Any],
    collect: Callable[[Target], Snapshot],
    now: str,
) -> tuple[list[dict[str, Any]], list[tuple[Target, Detection]], dict[str, str]]:
    """Pure-ish core: `collect` is injected so this is testable without a browser."""
    entries: list[dict[str, Any]] = []
    alerts: list[tuple[Target, Detection]] = []
    new_state = dict(state)

    for target in targets:
        try:
            snapshot = collect(target)
        except Exception:
            log.exception("target failed to render: %s", target.id)
            entries.append(carry_over(target, previous, now))
            continue

        detection = detect(new_state.get(target.id), snapshot.dates)

        if detection.status == NO_DATES:
            log.warning("no bookable dates found for %s", target.id)
            entries.append(carry_over(target, previous, now))
            continue

        entries.append(build_entry(target, snapshot, status="ok"))

        if detection.status == NEW_DAY:
            alerts.append((target, detection))

        # Never regress: a partial render must not re-arm an alert later.
        new_state[target.id] = max(new_state.get(target.id, ""), detection.new_max)

    return entries, alerts, new_state


def _event(target: Target, detection: Detection, now: str) -> dict[str, Any]:
    return {
        "at": now,
        "target_id": target.id,
        "label": target.label,
        "previous": detection.previous,
        "new_max": detection.new_max,
        "added": detection.added,
        "url": target.url,
    }


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    settings: Settings = load_settings()
    targets = load_targets(TARGETS_FILE)
    state = load_state(STATE_FILE)
    previous = load_snapshot(SNAPSHOT_FILE)
    now = datetime.now(ZoneInfo(settings.tz)).isoformat(timespec="seconds")

    with browser_session() as browser:

        def collect(target: Target) -> Snapshot:
            return collect_target(browser, target, get_adapter(target.site))

        entries, alerts, new_state = run_targets(targets, state, previous, collect, now)

    for target, detection in alerts:
        log.info("new booking day for %s -> %s", target.id, detection.new_max)
        telegram.send(settings, format_alert(target, detection))

    append_events(EVENTS_FILE, [_event(t, d, now) for t, d in alerts])
    save_state(STATE_FILE, new_state)
    save_snapshot(SNAPSHOT_FILE, entries, now)

    log.info("run complete: %d targets, %d alerts", len(entries), len(alerts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
