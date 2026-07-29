# pop-hunt Phase 1 — Monitor & Telegram Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that renders tracked cinema pages in headless Chromium every 30 minutes, detects when a cinema opens a new bookable day, and sends a Telegram alert.

**Architecture:** Each *watch target* (a URL) is rendered once by Playwright. A per-site adapter turns the rendered page into a `Snapshot` (bookable dates + movies + showtimes + posters). A pure `detect()` compares the furthest date against the last-seen furthest date in `state.json`; if it advanced, a Telegram alert fires. All pure logic (dates, detection, formatting, store) is isolated from the side-effecting layers (browser, HTTP, disk) so the core is testable with no network.

**Tech Stack:** Python 3.12, Playwright (Chromium), PyYAML, `requests`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-07-29-pop-hunt-cinema-monitor-design.md`

**Scope note:** This plan is Phase 1 only — the monitor and alerts. It produces working, useful software on its own (you get Telegram alerts). Phase 2 (the Vite + React 19 + TanStack Router dashboard on Cloudflare Pages) is a separate plan that consumes the `data/*.json` files written here.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `targets.yaml` | Watch targets (human-edited) |
| `src/pop_hunt/models.py` | `Showtime`, `Movie`, `Snapshot` dataclasses + JSON round-trip |
| `src/pop_hunt/dates.py` | Pure date-text → ISO parsing, incl. year inference |
| `src/pop_hunt/detector.py` | Pure new-day detection |
| `src/pop_hunt/config.py` | Load `targets.yaml` and env settings |
| `src/pop_hunt/store.py` | Read/write `state.json`, `data/snapshot.json`, `data/events.json` |
| `src/pop_hunt/notifiers/format.py` | Pure alert-text building |
| `src/pop_hunt/notifiers/telegram.py` | Telegram Bot API send |
| `src/pop_hunt/adapters/base.py` | `SiteAdapter` protocol + shared date-tab walker |
| `src/pop_hunt/adapters/scene.py` | Scene: click `LoadShowtimes` date tabs, parse experience blocks |
| `src/pop_hunt/adapters/vox.py` | VOX: fetch each `?d=YYYYMMDD` URL, parse `article.movie-compare` |
| `src/pop_hunt/adapters/premiere.py` | Premiere: select cinema, recover booking window |
| `src/pop_hunt/adapters/__init__.py` | site id → adapter registry |
| `src/pop_hunt/fetcher.py` | Playwright browser lifecycle + page load |
| `src/pop_hunt/main.py` | Run orchestration |
| `scripts/capture_fixtures.py` | Dev tool: save rendered HTML per target for tests |
| `.github/workflows/monitor.yml` | Cron, run, commit changed data |
| `README.md` | Setup instructions |

**Dependency order:** models → dates → detector → config → store → format → telegram → adapter protocol → fixtures → adapters (scene, vox, premiere) → fetcher → main → workflow. Tasks below follow this order, so every task depends only on already-built units.

**Registry sequencing:** Task 9 creates the `SiteAdapter` protocol ONLY. The
registry in `adapters/__init__.py` imports all three adapter modules, so writing
it before they exist would make `import pop_hunt.adapters` raise — which breaks
*test collection* for Tasks 11 and 12, not just the registry's own test. The
registry and its test are therefore written together in Task 13, once all three
adapters exist. The suite stays green after every task.

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/pop_hunt/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "pop-hunt"
version = "0.1.0"
description = "Alerts when a tracked cinema opens a new bookable day"
requires-python = ">=3.12"
dependencies = [
    "playwright>=1.47",
    "PyYAML>=6.0",
    "requests>=2.32",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create empty package files**

```bash
mkdir -p src/pop_hunt/adapters src/pop_hunt/notifiers tests/fixtures scripts data
touch src/pop_hunt/__init__.py src/pop_hunt/adapters/__init__.py src/pop_hunt/notifiers/__init__.py tests/__init__.py
```

- [ ] **Step 3: Install**

Run: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Expected: ends with `Successfully installed ... pop-hunt-0.1.0 ...`

- [ ] **Step 4: Verify pytest runs**

Run: `.venv/bin/pytest`
Expected: `no tests ran` (exit code 5). This confirms config is valid.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests
git commit -m "chore: scaffold pop-hunt package"
```

---

## Task 2: Data models

**Files:**
- Create: `src/pop_hunt/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from pop_hunt.models import Movie, Showtime, Snapshot


def test_showtime_round_trips_through_dict():
    st = Showtime(time="10:45am", experience="MAX", attributes=("3D",), available=True)
    assert Showtime.from_dict(st.to_dict()) == st


def test_showtime_defaults_to_available_with_no_experience():
    st = Showtime(time="7:00pm")
    assert st.experience is None
    assert st.attributes == ()
    assert st.available is True


def test_movie_round_trips_with_showtimes_keyed_by_date():
    movie = Movie(
        title="Spider-Man: Brand New Day",
        poster_url="https://example.test/p.jpg",
        rating="12+",
        runtime_min=140,
        language="English",
        showtimes={"2026-07-30": [Showtime(time="2:00pm", experience="GOLD")]},
    )
    assert Movie.from_dict(movie.to_dict()) == movie


def test_snapshot_round_trips():
    snap = Snapshot(
        target_id="vox-moe-spiderman",
        dates=["2026-07-30", "2026-07-31"],
        movies=[Movie(title="A Film")],
    )
    assert Snapshot.from_dict(snap.to_dict()) == snap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.models'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/models.py
"""Data model shared by the detector and the dashboard feed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Showtime:
    """A single screening. `available` is False when sold out or already past."""

    time: str
    experience: str | None = None
    attributes: tuple[str, ...] = ()
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "experience": self.experience,
            "attributes": list(self.attributes),
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Showtime:
        return cls(
            time=data["time"],
            experience=data.get("experience"),
            attributes=tuple(data.get("attributes") or ()),
            available=bool(data.get("available", True)),
        )


@dataclass(frozen=True)
class Movie:
    title: str
    poster_url: str | None = None
    rating: str | None = None
    runtime_min: int | None = None
    language: str | None = None
    showtimes: dict[str, list[Showtime]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "poster_url": self.poster_url,
            "rating": self.rating,
            "runtime_min": self.runtime_min,
            "language": self.language,
            "showtimes": {
                date: [st.to_dict() for st in times]
                for date, times in self.showtimes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Movie:
        return cls(
            title=data["title"],
            poster_url=data.get("poster_url"),
            rating=data.get("rating"),
            runtime_min=data.get("runtime_min"),
            language=data.get("language"),
            showtimes={
                date: [Showtime.from_dict(st) for st in times]
                for date, times in (data.get("showtimes") or {}).items()
            },
        )


@dataclass(frozen=True)
class Snapshot:
    """One render of one target: the dates that are bookable, and what's on."""

    target_id: str
    dates: list[str]
    movies: list[Movie]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "dates": list(self.dates),
            "movies": [m.to_dict() for m in self.movies],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            target_id=data["target_id"],
            dates=list(data.get("dates") or []),
            movies=[Movie.from_dict(m) for m in (data.get("movies") or [])],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/models.py tests/test_models.py
git commit -m "feat: add snapshot data model"
```

---

## Task 3: Date parsing

Two helpers, because the sites differ:

- `parse_dmy` — Scene renders machine-readable `30-07-2026`. Used by the Scene adapter (Task 11).
- `parse_day_month` — for strips that render `Thu 30 Jul` with **no year**, where the year must be inferred from today and roll forward across Dec→Jan.

VOX turned out to expose `d=YYYYMMDD` in its date links (Task 12) and Premiere
exposes ISO dates (Task 13), so neither needs `parse_day_month` today. It is
built here because Premiere's Strategy A (Task 13) may need it once its date
strip renders, and it is the documented fallback if any site drops its
machine-readable dates. If Task 13 lands on Strategy B and you want it gone,
delete it and its tests — nothing else imports it.

**Files:**
- Create: `src/pop_hunt/dates.py`
- Test: `tests/test_dates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dates.py
from datetime import date

import pytest

from pop_hunt.dates import parse_day_month, parse_dmy


def test_parse_dmy_converts_scene_format():
    assert parse_dmy("30-07-2026") == "2026-07-30"
    assert parse_dmy(" 01-08-2026 ") == "2026-08-01"


def test_parse_day_month_infers_current_year():
    assert parse_day_month("Thu 30 Jul", today=date(2026, 7, 29)) == "2026-07-30"


def test_parse_day_month_handles_zero_padded_day_and_no_weekday():
    assert parse_day_month("Sat 01 Aug", today=date(2026, 7, 29)) == "2026-08-01"
    assert parse_day_month("5 Aug", today=date(2026, 7, 29)) == "2026-08-05"


def test_parse_day_month_rolls_into_next_year_across_december():
    # In late December, a "02 Jan" tab means next year.
    assert parse_day_month("Fri 02 Jan", today=date(2026, 12, 28)) == "2027-01-02"


def test_parse_day_month_keeps_same_year_for_later_month():
    assert parse_day_month("Tue 03 Dec", today=date(2026, 12, 1)) == "2026-12-03"


def test_parse_day_month_rejects_unparseable_text():
    with pytest.raises(ValueError):
        parse_day_month("Coming Soon", today=date(2026, 7, 29))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.dates'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/dates.py
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
        # Weekday abbreviations never collide with month ones, which is what
        # makes this order-independent loop safe.
        if cleaned[:3] in _MONTHS:
            month = _MONTHS[cleaned[:3]]
        elif cleaned.isdigit() and len(cleaned) <= 2 and day is None:
            # First-wins and at most two digits: a trailing year token ("30 Jul
            # 2026") or a stray number must not overwrite the day.
            day = int(cleaned)
    if day is None or month is None or not 1 <= day <= 31:
        raise ValueError(f"cannot parse day/month from {text!r}")
    year = today.year + 1 if month < today.month else today.year
    return f"{year:04d}-{month:02d}-{day:02d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dates.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/dates.py tests/test_dates.py
git commit -m "feat: add date parsing with year inference"
```

---

## Task 4: Detector

The core rule. ISO `YYYY-MM-DD` strings sort chronologically as plain strings, so no date objects are needed here.

**Files:**
- Create: `src/pop_hunt/detector.py`
- Test: `tests/test_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_detector.py
from pop_hunt.detector import BASELINE, NEW_DAY, NO_CHANGE, NO_DATES, detect


def test_no_dates_when_page_yielded_nothing():
    result = detect("2026-08-05", [])
    assert result.status == NO_DATES
    assert result.new_day_opened is False
    assert result.new_max is None


def test_baseline_on_first_ever_run_does_not_alert():
    result = detect(None, ["2026-07-30", "2026-08-05"])
    assert result.status == BASELINE
    assert result.new_day_opened is False
    assert result.new_max == "2026-08-05"
    assert result.added == []


def test_no_change_when_furthest_date_is_unchanged():
    result = detect("2026-08-05", ["2026-07-30", "2026-08-05"])
    assert result.status == NO_CHANGE
    assert result.new_day_opened is False
    assert result.new_max == "2026-08-05"


def test_new_day_when_furthest_date_advances():
    result = detect("2026-08-05", ["2026-07-31", "2026-08-05", "2026-08-06"])
    assert result.status == NEW_DAY
    assert result.new_day_opened is True
    assert result.previous == "2026-08-05"
    assert result.new_max == "2026-08-06"
    assert result.added == ["2026-08-06"]


def test_new_day_reports_every_added_date_when_several_open_at_once():
    result = detect("2026-08-05", ["2026-08-06", "2026-08-07", "2026-08-08"])
    assert result.added == ["2026-08-06", "2026-08-07", "2026-08-08"]


def test_window_shrinking_is_not_a_new_day():
    # Furthest date went backwards (movie ending its run). Not an alert.
    result = detect("2026-08-05", ["2026-07-30", "2026-08-01"])
    assert result.status == NO_CHANGE
    assert result.new_day_opened is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.detector'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/detector.py
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

    Precondition: every date MUST be zero-padded fixed-width `YYYY-MM-DD`,
    which is what `dates.py` guarantees. Only then do ISO strings compare
    chronologically as plain strings. A single unpadded date such as
    "2026-8-6" would sort above every padded date that year, fire a spurious
    alert, and then suppress real ones until the year rolls over.
    """
    if not dates:
        return Detection(NO_DATES, False, previous_furthest, None, [])

    current_max = max(dates)

    if previous_furthest is None:
        # First time we have seen this target: record silently, never alert.
        return Detection(BASELINE, False, None, current_max, [])

    if current_max > previous_furthest:
        # Deduped: responsive sites often render the date strip twice
        # (desktop + mobile DOM), which would otherwise repeat in the alert.
        added = sorted({d for d in dates if d > previous_furthest})
        return Detection(NEW_DAY, True, previous_furthest, current_max, added)

    return Detection(NO_CHANGE, False, previous_furthest, current_max, [])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_detector.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/detector.py tests/test_detector.py
git commit -m "feat: add new-booking-day detector"
```

---

## Task 5: Config loading

**Files:**
- Create: `src/pop_hunt/config.py`
- Create: `targets.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest

from pop_hunt.config import load_settings, load_targets

SAMPLE = """
targets:
  - id: scene-district5-spiderman
    label: "Scene District 5 — Spider-Man"
    site: scene
    scope: movie
    url: "https://district5.scenecinemas.com/movie-details/spider-man-brand-new-day.html"
  - id: premiere-cima-arkan-spiderman
    label: "Premiere Cima Arkan — Spider-Man"
    site: premiere
    scope: movie
    cinema: "Cima Arkan"
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
"""


def test_load_targets_reads_all_fields(tmp_path):
    path = tmp_path / "targets.yaml"
    path.write_text(SAMPLE)

    targets = load_targets(path)

    assert [t.id for t in targets] == [
        "scene-district5-spiderman",
        "premiere-cima-arkan-spiderman",
    ]
    assert targets[0].site == "scene"
    assert targets[0].cinema is None
    assert targets[1].cinema == "Cima Arkan"


def test_load_targets_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "targets.yaml"
    path.write_text(
        'targets:\n'
        '  - {id: a, label: A, site: scene, url: "https://x.test"}\n'
        '  - {id: a, label: B, site: scene, url: "https://y.test"}\n'
    )
    with pytest.raises(ValueError, match="duplicate target id: a"):
        load_targets(path)


def test_settings_disabled_when_telegram_secrets_absent():
    settings = load_settings({})
    assert settings.telegram_enabled is False
    assert settings.tz == "Africa/Cairo"


def test_settings_enabled_when_both_telegram_secrets_present():
    settings = load_settings(
        {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1", "CHECK_TZ": "UTC"}
    )
    assert settings.telegram_enabled is True
    assert settings.tz == "UTC"


def test_settings_disabled_when_only_one_telegram_secret_present():
    assert load_settings({"TELEGRAM_BOT_TOKEN": "t"}).telegram_enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.config'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/config.py
"""Load watch targets from YAML and settings from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

DEFAULT_TZ = "Africa/Cairo"


@dataclass(frozen=True)
class Target:
    id: str
    label: str
    site: str
    url: str
    scope: str = "movie"
    cinema: str | None = None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    tz: str

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def load_targets(path: str | Path) -> list[Target]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    targets: list[Target] = []
    seen: set[str] = set()
    for entry in raw.get("targets") or []:
        target = Target(
            id=entry["id"],
            label=entry["label"],
            site=entry["site"],
            url=entry["url"],
            scope=entry.get("scope", "movie"),
            cinema=entry.get("cinema"),
        )
        if target.id in seen:
            raise ValueError(f"duplicate target id: {target.id}")
        seen.add(target.id)
        targets.append(target)
    return targets


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=env.get("TELEGRAM_CHAT_ID") or None,
        tz=env.get("CHECK_TZ") or DEFAULT_TZ,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Create the real `targets.yaml`**

```yaml
# targets.yaml — watch targets. Add or remove freely; `id` must be unique.
targets:
  - id: vox-moe-spiderman
    label: "VOX Mall of Egypt — Spider-Man: Brand New Day"
    site: vox
    scope: movie
    url: "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man-brand-new-day"

  - id: vox-moe-all
    label: "VOX Mall of Egypt — all movies"
    site: vox
    scope: cinema
    url: "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt"

  - id: scene-district5-spiderman
    label: "Scene District 5 — Spider-Man: Brand New Day"
    site: scene
    scope: movie
    url: "https://district5.scenecinemas.com/movie-details/spider-man-brand-new-day.html"

  - id: premiere-cima-arkan-spiderman
    label: "Premiere Cima Arkan — Spider-Man: Brand New Day"
    site: premiere
    scope: movie
    cinema: "Cima Arkan"
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
```

- [ ] **Step 6: Verify the real file loads**

Run: `.venv/bin/python -c "from pop_hunt.config import load_targets; print([t.id for t in load_targets('targets.yaml')])"`
Expected: `['vox-moe-spiderman', 'vox-moe-all', 'scene-district5-spiderman', 'premiere-cima-arkan-spiderman']`

- [ ] **Step 7: Commit**

```bash
git add src/pop_hunt/config.py tests/test_config.py targets.yaml
git commit -m "feat: add target and settings loading"
```

---

## Task 6: Store (state, snapshot, events)

Three files with different write rules. The important one is **write-if-changed** on the snapshot: without it every 30-minute run would create a commit.

**Files:**
- Create: `src/pop_hunt/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
import json

from pop_hunt.store import (
    append_events,
    load_events,
    load_snapshot,
    load_state,
    save_snapshot,
    save_state,
)


def test_load_state_returns_empty_dict_when_file_absent(tmp_path):
    assert load_state(tmp_path / "state.json") == {}


def test_load_state_returns_empty_dict_when_file_is_corrupt(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    assert load_state(path) == {}


def test_save_state_writes_and_reports_change(tmp_path):
    path = tmp_path / "state.json"
    assert save_state(path, {"a": "2026-08-05"}) is True
    assert load_state(path) == {"a": "2026-08-05"}


def test_save_state_is_a_noop_when_unchanged(tmp_path):
    path = tmp_path / "state.json"
    save_state(path, {"a": "2026-08-05"})
    before = path.read_text()
    assert save_state(path, {"a": "2026-08-05"}) is False
    assert path.read_text() == before


def test_save_snapshot_ignores_generated_at_when_deciding_to_write(tmp_path):
    path = tmp_path / "snapshot.json"
    targets = [{"id": "a", "dates": ["2026-08-05"]}]
    assert save_snapshot(path, targets, "2026-07-30T09:00:00+03:00") is True

    # Same content, later timestamp -> must NOT rewrite (avoids a commit per run).
    assert save_snapshot(path, targets, "2026-07-30T09:30:00+03:00") is False
    assert json.loads(path.read_text())["generated_at"] == "2026-07-30T09:00:00+03:00"


def test_save_snapshot_writes_when_content_changes(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(path, [{"id": "a", "dates": ["2026-08-05"]}], "t1")
    assert save_snapshot(path, [{"id": "a", "dates": ["2026-08-06"]}], "t2") is True
    assert json.loads(path.read_text())["generated_at"] == "t2"


def test_load_snapshot_returns_empty_shape_when_absent(tmp_path):
    assert load_snapshot(tmp_path / "snapshot.json") == {
        "generated_at": None,
        "targets": [],
    }


def test_append_events_puts_newest_first(tmp_path):
    path = tmp_path / "events.json"
    append_events(path, [{"at": "t1", "target_id": "a"}])
    append_events(path, [{"at": "t2", "target_id": "b"}])
    assert [e["at"] for e in load_events(path)] == ["t2", "t1"]


def test_append_events_is_a_noop_for_empty_input(tmp_path):
    path = tmp_path / "events.json"
    assert append_events(path, []) is False
    assert path.exists() is False


def test_append_events_caps_the_log(tmp_path):
    path = tmp_path / "events.json"
    append_events(path, [{"at": f"t{i}"} for i in range(250)])
    assert len(load_events(path)) == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.store'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/store.py
"""Persistence for detection state and the dashboard data files.

Writes are change-aware: the workflow commits these files, so rewriting an
identical file every 30 minutes would produce a commit per run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_EVENTS = 200


def _empty_snapshot() -> dict[str, Any]:
    """Fresh each call - a module-level constant would be shared and mutable."""
    return {"generated_at": None, "targets": []}


def _read_json(path: str | Path, default: Any) -> Any:
    """Return the parsed file, or `default` if it is missing or unusable.

    Wrong-type JSON must fall back too, not just malformed JSON: these files
    are committed to the repo, so a bad one is sticky and would otherwise
    crash every run until a human intervened. `json.JSONDecodeError` subclasses
    `ValueError`, and so does `UnicodeDecodeError` on a binary file.
    """
    file = Path(path)
    if not file.exists():
        return default
    try:
        value = json.loads(file.read_text())
    except ValueError:
        return default
    return value if isinstance(value, type(default)) else default


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
    return _read_json(path, _empty_snapshot())


def save_snapshot(
    path: str | Path, targets: list[dict[str, Any]], generated_at: str
) -> bool:
    """Write the dashboard feed, ignoring `generated_at` when comparing.

    Only a real content change should touch the file. `targets` is normalised
    through JSON first: any value that changes type on a round trip (a tuple
    becoming a list) would otherwise compare unequal forever and produce a
    commit every 30 minutes - the exact thing write-if-changed prevents.
    """
    targets = json.loads(json.dumps(targets))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/store.py tests/test_store.py
git commit -m "feat: add change-aware persistence layer"
```

---

## Task 7: Alert formatting

Telegram is sent with `parse_mode=HTML`, so any `&`, `<` or `>` in a label must be escaped or the API rejects the message.

**Files:**
- Create: `src/pop_hunt/notifiers/format.py`
- Test: `tests/test_format.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_format.py
from pop_hunt.config import Target
from pop_hunt.detector import detect
from pop_hunt.notifiers.format import format_alert

TARGET = Target(
    id="scene-district5-spiderman",
    label="Scene District 5 — Spider-Man",
    site="scene",
    url="https://district5.scenecinemas.com/movie-details/spider-man.html",
)


def test_alert_contains_label_dates_and_url():
    detection = detect("2026-08-05", ["2026-08-05", "2026-08-06"])
    text = format_alert(TARGET, detection)

    assert "New booking day" in text
    assert "Scene District 5 — Spider-Man" in text
    assert "2026-08-06" in text
    assert "was 2026-08-05" in text
    assert TARGET.url in text


def test_alert_lists_every_added_date():
    detection = detect("2026-08-05", ["2026-08-06", "2026-08-07"])
    assert "2026-08-06, 2026-08-07" in format_alert(TARGET, detection)


def test_alert_escapes_html_in_the_label():
    target = Target(id="x", label="Cinema <B> & Co", site="scene", url="https://x.test")
    detection = detect("2026-08-05", ["2026-08-06"])
    text = format_alert(target, detection)

    assert "&lt;B&gt;" in text
    assert "&amp;" in text
    assert "<B>" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.notifiers.format'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/notifiers/format.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_format.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/notifiers/format.py tests/test_format.py
git commit -m "feat: add telegram alert formatting"
```

---

## Task 8: Telegram notifier

Must never crash the run: a failed send is logged and reported as `False`, and the run continues so data still persists.

**Files:**
- Create: `src/pop_hunt/notifiers/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telegram.py
from pop_hunt.config import Settings
from pop_hunt.notifiers import telegram

ENABLED = Settings(telegram_bot_token="tok", telegram_chat_id="42", tz="Africa/Cairo")
DISABLED = Settings(telegram_bot_token=None, telegram_chat_id=None, tz="Africa/Cairo")


class _FakeResponse:
    def __init__(self, error: Exception | None = None):
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error


def test_send_posts_to_the_bot_api(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(telegram.requests, "post", fake_post)

    assert telegram.send(ENABLED, "hello") is True
    assert captured["url"] == "https://api.telegram.org/bottok/sendMessage"
    assert captured["json"]["chat_id"] == "42"
    assert captured["json"]["text"] == "hello"
    assert captured["json"]["parse_mode"] == "HTML"


def test_send_skips_when_not_configured(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("must not call the API when unconfigured")

    monkeypatch.setattr(telegram.requests, "post", fail)
    assert telegram.send(DISABLED, "hello") is False


def test_send_returns_false_instead_of_raising_on_api_error(monkeypatch):
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, json, timeout: _FakeResponse(RuntimeError("429")),
    )
    assert telegram.send(ENABLED, "hello") is False


def test_send_returns_false_instead_of_raising_on_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("connection reset")

    monkeypatch.setattr(telegram.requests, "post", boom)
    assert telegram.send(ENABLED, "hello") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.notifiers.telegram'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/notifiers/telegram.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_telegram.py -v`
Expected: PASS — 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/notifiers/telegram.py tests/test_telegram.py
git commit -m "feat: add telegram notifier"
```

---

## Task 9: Adapter protocol and registry

**Files:**
- Create: `src/pop_hunt/adapters/base.py`
- Modify: `src/pop_hunt/adapters/__init__.py`
- Test: `tests/test_adapter_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapter_registry.py
import pytest

from pop_hunt.adapters import get_adapter


def test_registry_returns_an_adapter_per_known_site():
    for site in ("scene", "vox", "premiere"):
        assert get_adapter(site).site_id == site


def test_registry_rejects_unknown_sites():
    with pytest.raises(KeyError, match="unknown site"):
        get_adapter("odeon")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_adapter_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_adapter'`

- [ ] **Step 3: Write `base.py`**

```python
# src/pop_hunt/adapters/base.py
"""The contract every site adapter implements."""

from __future__ import annotations

from typing import Protocol

from pop_hunt.config import Target
from pop_hunt.models import Snapshot


class SiteAdapter(Protocol):
    """Turns a rendered cinema page into a Snapshot.

    Implementations may drive the page (clicking date tabs) because dates are
    switched client-side on all three sites.
    """

    site_id: str

    def collect(self, page, target: Target) -> Snapshot:
        """Return the bookable dates and what's showing on them."""
        ...
```

- [ ] **Step 4: Write the registry**

Note: the three adapter modules do not exist yet, so this import fails until Tasks 11-13 are done. Write the registry now; its test is re-run and goes green at the end of Task 13.

```python
# src/pop_hunt/adapters/__init__.py
"""Registry mapping a target's `site` value to its adapter."""

from __future__ import annotations

from pop_hunt.adapters.base import SiteAdapter
from pop_hunt.adapters.premiere import PremiereAdapter
from pop_hunt.adapters.scene import SceneAdapter
from pop_hunt.adapters.vox import VoxAdapter

_ADAPTERS: dict[str, SiteAdapter] = {
    "scene": SceneAdapter(),
    "vox": VoxAdapter(),
    "premiere": PremiereAdapter(),
}


def get_adapter(site: str) -> SiteAdapter:
    try:
        return _ADAPTERS[site]
    except KeyError:
        raise KeyError(f"unknown site: {site!r}") from None


__all__ = ["SiteAdapter", "get_adapter"]
```

- [ ] **Step 5: Commit the protocol only**

The registry test stays red until Task 13. Commit `base.py` now; `__init__.py` is committed with Task 13.

```bash
git add src/pop_hunt/adapters/base.py tests/test_adapter_registry.py
git commit -m "feat: add site adapter protocol"
```

---

## Task 10: Fixture capture script

Adapters are written against **saved real HTML**, so tests never touch the network. This script produces those fixtures.

**Files:**
- Create: `scripts/capture_fixtures.py`

- [ ] **Step 1: Install the browser**

Run: `.venv/bin/playwright install --with-deps chromium`
Expected: downloads Chromium; ends without error.

- [ ] **Step 2: Write the script**

```python
# scripts/capture_fixtures.py
"""Dev tool: save each target's rendered HTML into tests/fixtures/.

Usage:  python scripts/capture_fixtures.py [target_id ...]

Re-run this when a cinema redesigns its site and an adapter starts failing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pop_hunt.config import load_targets

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    targets = [t for t in load_targets("targets.yaml") if not wanted or t.id in wanted]
    if not targets:
        print("no matching targets")
        return 1

    FIXTURES.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        for target in targets:
            page = context.new_page()
            print(f"-> {target.id}: {target.url}")
            page.goto(target.url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(3_000)
            out = FIXTURES / f"{target.id}.html"
            out.write_text(page.content(), encoding="utf-8")
            print(f"   saved {out.relative_to(Path.cwd())} ({out.stat().st_size} bytes)")
            page.close()
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 3: Capture the fixtures**

Run: `.venv/bin/python scripts/capture_fixtures.py`
Expected: four `saved tests/fixtures/<id>.html` lines, each well over 10,000 bytes.

If a page saves but is nearly empty, the site blocked the headless browser — increase the `wait_for_timeout` and re-run that one target only.

- [ ] **Step 4: Commit**

Fixtures are committed so tests are reproducible.

```bash
git add scripts/capture_fixtures.py tests/fixtures
git commit -m "chore: add fixture capture script and initial fixtures"
```

---

## Task 11: Scene adapter

**Verified DOM (captured 2026-07-29)** — confirm against your fixture before relying on it:

- Date tabs: `a[href^="javascript:LoadShowtimes"]` wrapping `li.calanderdays`, with `id="data-30-07-2026"` and `<span class="daysm">30-07-2026</span>`. Selected tab carries `active` in its class.
- Switching date calls the page function `LoadShowtimes('30-07-2026')`.
- Showtimes: `div.showtimes` containing `div.ex_vip_content` (label `span.ex_vip` = "Premiere") and `div.ex_stand_content` (label `span.ex_stand` = "Standard & Deluxe"); each has `ul > li > a` per time. A sold-out time carries class `showtime_soldout`.

**Files:**
- Create: `src/pop_hunt/adapters/scene.py`
- Create: `tests/fixtures/scene_day.html`
- Test: `tests/test_scene_adapter.py`

- [ ] **Step 1: Create a minimal structural fixture**

This mirrors the real markup above, trimmed to what the parser needs.

```html
<!-- tests/fixtures/scene_day.html -->
<div class="calanderdiv">
  <ul>
    <a href="javascript:LoadShowtimes('30-07-2026')">
      <li class="calanderdays  active " id="data-30-07-2026">
        <span class="daysm"> Thu</span>
        <span class="daylg">30 Jul</span>
        <span class="daysm">30-07-2026</span>
      </li>
    </a>
    <a href="javascript:LoadShowtimes('31-07-2026')">
      <li class="calanderdays " id="data-31-07-2026">
        <span class="daysm"> Fri</span>
        <span class="daylg">31 Jul</span>
        <span class="daysm">31-07-2026</span>
      </li>
    </a>
  </ul>
</div>
<div class="col-12 showtimes">
  <div class="ex_vip_content mt-3">
    <span class="ex_vip">Premiere</span>
    <ul>
      <li><a class="vip showtime_soldout">10:30 AM</a></li>
      <li><a class="vip">01:00 PM</a></li>
    </ul>
  </div>
  <div class="ex_stand_content mt-3">
    <span class="ex_stand">Standard &amp; Deluxe</span>
    <ul>
      <li><a>12:00 PM</a></li>
    </ul>
  </div>
</div>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_scene_adapter.py
from pathlib import Path

from pop_hunt.adapters.scene import (
    SceneAdapter,
    parse_showtimes,
    parse_tab_dates,
)

FIXTURES = Path(__file__).parent / "fixtures"
DAY_HTML = (FIXTURES / "scene_day.html").read_text()


def test_parse_tab_dates_returns_iso_dates_in_order():
    assert parse_tab_dates(DAY_HTML) == ["2026-07-30", "2026-07-31"]


def test_parse_showtimes_reads_times_and_experiences():
    showtimes = parse_showtimes(DAY_HTML)
    assert [s.time for s in showtimes] == ["10:30 AM", "01:00 PM", "12:00 PM"]
    assert showtimes[0].experience == "Premiere"
    assert showtimes[2].experience == "Standard & Deluxe"


def test_parse_showtimes_marks_sold_out_times_unavailable():
    showtimes = parse_showtimes(DAY_HTML)
    assert showtimes[0].available is False
    assert showtimes[1].available is True


def test_parse_showtimes_returns_empty_list_when_no_showtimes_present():
    assert parse_showtimes("<div class='showtimes'></div>") == []


def test_adapter_declares_its_site_id():
    assert SceneAdapter().site_id == "scene"


def test_real_fixture_still_yields_dates_and_showtimes():
    """Guards against a site redesign silently breaking the selectors."""
    html = (FIXTURES / "scene-district5-spiderman.html").read_text()
    assert len(parse_tab_dates(html)) >= 1
    assert len(parse_showtimes(html)) >= 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_scene_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.adapters.scene'`

- [ ] **Step 4: Write the implementation**

Parsing uses regular expressions over the HTML string so the pure functions are testable without a browser; the adapter only uses Playwright to click through date tabs.

```python
# src/pop_hunt/adapters/scene.py
"""Scene Cinemas (scenecinemas.com).

Dates are tabs that call the page function LoadShowtimes('DD-MM-YYYY');
showtimes for the selected date render into div.showtimes, grouped into
experience blocks (Premiere, Standard & Deluxe).
"""

from __future__ import annotations

import re

from pop_hunt.config import Target
from pop_hunt.dates import parse_dmy
from pop_hunt.models import Movie, Showtime, Snapshot

SITE_ID = "scene"

_TAB_DATE = re.compile(r"LoadShowtimes\('(\d{2}-\d{2}-\d{4})'\)")
_EXPERIENCE_BLOCK = re.compile(
    r'<div class="(ex_\w+)_content.*?</div>', re.DOTALL | re.IGNORECASE
)
_EXPERIENCE_LABEL = re.compile(r'<span class="ex_\w+">(.*?)</span>', re.DOTALL)
_SHOWTIME = re.compile(
    r'<a\b([^>]*)>\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*</a>', re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    from html import unescape

    return unescape(_TAG.sub("", fragment)).strip()


def parse_tab_dates(html: str) -> list[str]:
    """Every date tab on the page, as ISO dates, in document order."""
    seen: list[str] = []
    for raw in _TAB_DATE.findall(html):
        iso = parse_dmy(raw)
        if iso not in seen:
            seen.append(iso)
    return seen


def parse_showtimes(html: str) -> list[Showtime]:
    """Showtimes currently rendered, tagged with their experience."""
    showtimes: list[Showtime] = []
    for block in _EXPERIENCE_BLOCK.finditer(html):
        fragment = block.group(0)
        label_match = _EXPERIENCE_LABEL.search(fragment)
        experience = _text(label_match.group(1)) if label_match else None
        for attrs, time_text in _SHOWTIME.findall(fragment):
            showtimes.append(
                Showtime(
                    time=" ".join(time_text.split()),
                    experience=experience,
                    available="showtime_soldout" not in attrs,
                )
            )
    return showtimes


def parse_movie_meta(html: str) -> Movie:
    """Title and poster for the single movie this page is about."""
    title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    title = _text(title_match.group(1)) if title_match else "Unknown"
    poster_match = re.search(
        r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.IGNORECASE
    )
    return Movie(title=title, poster_url=poster_match.group(1) if poster_match else None)


class SceneAdapter:
    site_id = SITE_ID

    def collect(self, page, target: Target) -> Snapshot:
        html = page.content()
        movie = parse_movie_meta(html)
        dates_with_showtimes: list[str] = []
        showtimes_by_date: dict[str, list[Showtime]] = {}

        for iso in parse_tab_dates(html):
            dmy = f"{iso[8:10]}-{iso[5:7]}-{iso[0:4]}"
            page.click(f'a[href="javascript:LoadShowtimes(\'{dmy}\')"]')
            page.wait_for_timeout(1_500)
            showtimes = parse_showtimes(page.content())
            if showtimes:
                dates_with_showtimes.append(iso)
                showtimes_by_date[iso] = showtimes

        return Snapshot(
            target_id=target.id,
            dates=sorted(dates_with_showtimes),
            movies=[
                Movie(
                    title=movie.title,
                    poster_url=movie.poster_url,
                    showtimes=showtimes_by_date,
                )
            ],
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_scene_adapter.py -v`
Expected: PASS — 6 passed

If `test_real_fixture_still_yields_dates_and_showtimes` fails, open `tests/fixtures/scene-district5-spiderman.html` and compare its markup to the minimal fixture; adjust the regexes to match reality, not the other way round.

- [ ] **Step 6: Commit**

```bash
git add src/pop_hunt/adapters/scene.py tests/test_scene_adapter.py tests/fixtures/scene_day.html
git commit -m "feat: add scene cinemas adapter"
```

---
## Task 12: VOX adapter

**Verified DOM (captured 2026-07-29).** VOX is the *easiest* of the three, because
its date strip is real links carrying the date as a query param — no year
inference, no clicking:

```html
<ol>
  <li><span>Tomorrow</span></li>                                <!-- selected day: NO date! -->
  <li><a href="/showtimes?c=mall-of-egypt&m=spider-man-brand-new-day&d=20260731">Fri 31 Jul</a></li>
  <li><a href="...&d=20260801">Sat 01 Aug</a></li>
</ol>
```

Each movie is an `<article class="movie-compare">`:

```html
<article class="movie-compare" data-slug="spider-man-brand-new-day">
  <aside class="movie-hero">
    <img class="hero" src="https://assets.voxcinemas.com/heroes/B_HO00013065_...jpg">
    <div>
      <h2>Spider-Man: Brand New Day</h2>
      <span class="classification c-12p white fixed">12+</span>
      <span class="tag">English</span>
      <span class="tag">140 min</span>
  <div class="dates">
    <ol class="showtimes">
      <li>
        <strong>MAX</strong>                                     <!-- experience -->
        <ol>
          <li data-id="0028-557346"><span class="action showtime unavailable">10:45am</span></li>
          <li data-id="0028-557347"><a class="action showtime" href="https://egy.voxcinemas.com/booking/0028-557347">2:00pm </a></li>
        </ol>
```

**Two consequences that shape the implementation:**

1. **Navigate, don't click.** Visiting `…&d=YYYYMMDD` directly is far more robust
   than clicking a tab and waiting for JS.
2. **The selected day has no date in the strip** — it renders as `Today`/`Tomorrow`.
   The strip is always contiguous days, so the displayed day is
   `min(link_dates) - 1 day`. Detection is unaffected either way, because the
   *furthest* date is always among the links.

**Files:**
- Create: `src/pop_hunt/adapters/vox.py`
- Create: `tests/fixtures/vox_day.html`
- Test: `tests/test_vox_adapter.py`

- [ ] **Step 1: Create the minimal structural fixture**

```html
<!-- tests/fixtures/vox_day.html -->
<ol>
  <li><span>Tomorrow</span></li>
  <li><a href="/showtimes?c=mall-of-egypt&amp;m=spider-man&amp;d=20260731">Fri 31 Jul</a></li>
  <li><a href="/showtimes?c=mall-of-egypt&amp;m=spider-man&amp;d=20260801">Sat 01 Aug</a></li>
</ol>
<article class="movie-compare" data-slug="spider-man-brand-new-day">
  <aside class="movie-hero">
    <img class="hero" src="https://assets.voxcinemas.com/heroes/spidey.jpg" alt="">
    <div>
      <h2>Spider-Man: Brand New Day</h2>
      <span class="classification c-12p white fixed">12+</span>
      <span class="tag">English</span>
      <span class="tag">140 min</span>
    </div>
  </aside>
  <div class="dates">
    <ol class="showtimes">
      <li>
        <strong>MAX</strong>
        <ol>
          <li data-id="a1"><span class="action showtime unavailable">10:45am</span></li>
          <li data-id="a2"><a class="action showtime" href="/booking/a2">2:00pm </a></li>
        </ol>
      </li>
      <li>
        <strong>Standard</strong>
        <ol>
          <li data-id="b1"><a class="action showtime" href="/booking/b1">12:00pm</a></li>
          <li data-id="b2"><a class="action showtime" href="/booking/b2">1:30pm <sup>3D</sup></a></li>
        </ol>
      </li>
    </ol>
  </div>
</article>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_vox_adapter.py
from pathlib import Path

from pop_hunt.adapters.vox import (
    VoxAdapter,
    date_url,
    parse_date_links,
    parse_movies,
    parse_showtimes,
    preceding_day,
)

FIXTURES = Path(__file__).parent / "fixtures"
DAY_HTML = (FIXTURES / "vox_day.html").read_text()


def test_parse_date_links_reads_the_d_query_param():
    assert parse_date_links(DAY_HTML) == ["2026-07-31", "2026-08-01"]


def test_parse_date_links_is_empty_when_no_strip_present():
    assert parse_date_links("<div>nothing</div>") == []


def test_preceding_day_recovers_the_selected_day():
    # The selected tab renders as "Tomorrow" with no date; it is the day before
    # the first link.
    assert preceding_day("2026-07-31") == "2026-07-30"
    assert preceding_day("2026-08-01") == "2026-07-31"
    assert preceding_day("2026-01-01") == "2025-12-31"


def test_date_url_sets_the_d_param_without_duplicating_it():
    base = "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man"
    assert date_url(base, "2026-08-01").endswith("d=20260801")
    already = base + "&d=20260731"
    result = date_url(already, "2026-08-01")
    assert result.count("d=") == 1
    assert result.endswith("d=20260801")


def test_parse_showtimes_reads_times_and_experiences():
    showtimes = parse_showtimes(DAY_HTML)
    assert [s.time for s in showtimes] == ["10:45am", "2:00pm", "12:00pm", "1:30pm"]
    assert showtimes[0].experience == "MAX"
    assert showtimes[2].experience == "Standard"


def test_parse_showtimes_marks_unavailable_times():
    showtimes = parse_showtimes(DAY_HTML)
    assert showtimes[0].available is False
    assert showtimes[1].available is True


def test_parse_showtimes_captures_3d_attribute():
    showtimes = parse_showtimes(DAY_HTML)
    assert showtimes[3].attributes == ("3D",)
    assert showtimes[1].attributes == ()


def test_parse_movies_reads_title_poster_and_metadata():
    movies = parse_movies(DAY_HTML)
    assert len(movies) == 1
    movie = movies[0]
    assert movie.title == "Spider-Man: Brand New Day"
    assert movie.poster_url == "https://assets.voxcinemas.com/heroes/spidey.jpg"
    assert movie.rating == "12+"
    assert movie.language == "English"
    assert movie.runtime_min == 140


def test_adapter_declares_its_site_id():
    assert VoxAdapter().site_id == "vox"


def test_real_fixture_still_yields_dates_and_showtimes():
    """Guards against a site redesign silently breaking the selectors."""
    html = (FIXTURES / "vox-moe-spiderman.html").read_text()
    assert len(parse_date_links(html)) >= 1
    assert len(parse_showtimes(html)) >= 1
    assert len(parse_movies(html)) >= 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_vox_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.adapters.vox'`

- [ ] **Step 4: Write the implementation**

```python
# src/pop_hunt/adapters/vox.py
"""VOX Cinemas (voxcinemas.com).

The date strip is a list of links carrying the date as `?...&d=YYYYMMDD`, so
each day is fetched by URL rather than by clicking a tab. The currently
displayed day is NOT in the strip - it renders as "Today"/"Tomorrow" - so it is
recovered as the day before the first link.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pop_hunt.config import Target
from pop_hunt.models import Movie, Showtime, Snapshot

SITE_ID = "vox"

_DATE_PARAM = re.compile(r"[?&]d=(\d{8})")
_ARTICLE = re.compile(r'<article\b[^>]*\bmovie-compare\b.*?</article>', re.DOTALL)
_TITLE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.DOTALL)
_POSTER = re.compile(r'<img\b[^>]*\bclass="[^"]*\bhero\b[^"]*"[^>]*\bsrc="([^"]+)"')
_RATING = re.compile(r'<span\b[^>]*\bclass="[^"]*\bclassification\b[^"]*"[^>]*>(.*?)</span>', re.DOTALL)
_TAG = re.compile(r'<span\b[^>]*\bclass="[^"]*\btag\b[^"]*"[^>]*>(.*?)</span>', re.DOTALL)
_RUNTIME = re.compile(r"(\d+)\s*min", re.IGNORECASE)
_EXPERIENCE = re.compile(r"<strong\b[^>]*>(.*?)</strong>", re.DOTALL)
_SHOWTIME = re.compile(
    r'<(a|span)\b([^>]*\bshowtime\b[^>]*)>(.*?)</\1>', re.DOTALL | re.IGNORECASE
)
_TIME_TEXT = re.compile(r"(\d{1,2}:\d{2}\s*(?:am|pm))", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return unescape(_TAGS.sub(" ", fragment)).strip()


def parse_date_links(html: str) -> list[str]:
    """ISO dates from the `d=YYYYMMDD` query param on each date-strip link."""
    dates: list[str] = []
    for raw in _DATE_PARAM.findall(html):
        iso = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        if iso not in dates:
            dates.append(iso)
    return sorted(dates)


def preceding_day(iso: str) -> str:
    """The day before `iso` - recovers the day the strip shows as Today/Tomorrow."""
    return (date.fromisoformat(iso) - timedelta(days=1)).isoformat()


def date_url(url: str, iso: str) -> str:
    """`url` with its `d` param replaced by `iso` (as YYYYMMDD)."""
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "d"]
    query.append(("d", iso.replace("-", "")))
    return urlunparse(parts._replace(query=urlencode(query)))


def _experience_groups(fragment: str):
    """Yield (experience, body) - split on <strong> markers.

    Splitting on markers rather than matching </li> avoids the nested-list
    problem: the experience <li> contains another <ol> of times.
    """
    marks = list(_EXPERIENCE.finditer(fragment))
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(fragment)
        yield _text(mark.group(1)), fragment[mark.end() : end]


def parse_showtimes(html: str) -> list[Showtime]:
    """Showtimes rendered for the currently displayed date."""
    showtimes: list[Showtime] = []
    for experience, body in _experience_groups(html):
        for _tag, attrs, inner in _SHOWTIME.findall(body):
            time_match = _TIME_TEXT.search(_text(inner))
            if not time_match:
                continue
            inner_text = _text(inner)
            attributes = ("3D",) if "3D" in inner_text.upper() else ()
            showtimes.append(
                Showtime(
                    time=" ".join(time_match.group(1).split()),
                    experience=experience or None,
                    attributes=attributes,
                    available="unavailable" not in attrs,
                )
            )
    return showtimes


def parse_movies(html: str) -> list[Movie]:
    """One Movie per <article class="movie-compare"> on the page."""
    movies: list[Movie] = []
    for article in _ARTICLE.findall(html):
        title_match = _TITLE.search(article)
        if not title_match:
            continue
        tags = [_text(t) for t in _TAG.findall(article)]
        runtime = next((_RUNTIME.search(t) for t in tags if _RUNTIME.search(t)), None)
        language = next((t for t in tags if not _RUNTIME.search(t)), None)
        poster = _POSTER.search(article)
        rating = _RATING.search(article)
        movies.append(
            Movie(
                title=_text(title_match.group(1)),
                poster_url=poster.group(1) if poster else None,
                rating=_text(rating.group(1)) if rating else None,
                runtime_min=int(runtime.group(1)) if runtime else None,
                language=language,
            )
        )
    return movies


class VoxAdapter:
    site_id = SITE_ID

    def collect(self, page, target: Target) -> Snapshot:
        html = page.content()
        link_dates = parse_date_links(html)

        # The displayed day is not in the strip; it precedes the first link.
        candidates = list(link_dates)
        if link_dates:
            candidates.insert(0, preceding_day(link_dates[0]))

        titles: dict[str, Movie] = {m.title: m for m in parse_movies(html)}
        showtimes_by_date: dict[str, list[Showtime]] = {}
        dates_with_showtimes: list[str] = []

        for iso in candidates:
            page.goto(date_url(target.url, iso), wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(1_500)
            day_html = page.content()
            showtimes = parse_showtimes(day_html)
            if not showtimes:
                continue
            dates_with_showtimes.append(iso)
            showtimes_by_date[iso] = showtimes
            for movie in parse_movies(day_html):
                titles.setdefault(movie.title, movie)

        movies = [
            Movie(
                title=movie.title,
                poster_url=movie.poster_url,
                rating=movie.rating,
                runtime_min=movie.runtime_min,
                language=movie.language,
                showtimes=showtimes_by_date,
            )
            for movie in titles.values()
        ]

        return Snapshot(
            target_id=target.id,
            dates=sorted(dates_with_showtimes),
            movies=movies,
        )
```

Note on `collect`: for a **movie-scope** target there is one article, so attaching
`showtimes_by_date` to it is exact. For a **cinema-scope** target (many articles)
the showtimes are not split per movie — that is a known Phase 1 simplification,
recorded in "Known limitations" at the end of this plan. Detection is unaffected;
only the dashboard's per-movie breakdown is coarse for cinema-scope targets.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_vox_adapter.py -v`
Expected: PASS — 10 passed

- [ ] **Step 6: Commit**

```bash
git add src/pop_hunt/adapters/vox.py tests/test_vox_adapter.py tests/fixtures/vox_day.html
git commit -m "feat: add vox cinemas adapter"
```

---

## Task 13: Premiere adapter

**Read this before starting — Premiere is the hard one.**

Investigation on 2026-07-29 established:

- The page is a Next.js SPA. On load it renders **"Invalid Date"** and a
  `CHOOSE YOUR CINEMA` list; no dates or showtimes exist in the DOM yet.
- The cinema chooser is a row of plain `<button>` elements whose only stable
  handle is their **text** (`Nile Cinema`, `Premiere Plaza`, `Galaxy elManial`,
  `Premiere Point90`, `Cima Arkan`). Their class attribute is generated utility
  CSS and must **not** be used as a selector.
- Clicking `Cima Arkan` in the in-app browser did **not** cause showtimes to
  render within a few seconds, and no XHR to the backend was observed. The cause
  was not established — it may need a longer wait, a second interaction, or a
  real user-agent.
- The embedded Next.js payload **does** contain the booking window as ISO dates
  (`2026-07-29` … `2026-08-05` were present, alongside unrelated dates such as
  other films' release dates), so the data reaches the client even before the
  DOM shows it.

Because of that last point there are two viable strategies. **Try A first.**

| | Strategy A — drive the UI | Strategy B — read the payload |
|---|---|---|
| How | Click the cinema button, wait, parse the rendered date strip and showtimes | Regex the ISO dates out of the embedded `<script>` payload |
| Pros | Gives movies + showtimes for the dashboard | Works even if the UI never renders |
| Cons | May not render headless | Dates only; must filter out unrelated dates |

**Files:**
- Create: `src/pop_hunt/adapters/premiere.py`
- Create: `tests/fixtures/premiere_day.html`
- Test: `tests/test_premiere_adapter.py`
- Modify: `src/pop_hunt/adapters/__init__.py` (written in Task 9)

- [ ] **Step 1: Determine which strategy works, using a real browser**

```bash
.venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright

URL = "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(user_agent=UA, locale="en-GB").new_page()
    page.goto(URL, wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(3_000)

    button = page.get_by_role("button", name="Cima Arkan", exact=True)
    print("button visible:", button.is_visible())
    button.click()
    page.wait_for_timeout(6_000)          # generous: the SPA may be slow

    html = page.content()
    open("tests/fixtures/premiere-cima-arkan-spiderman.html", "w").write(html)

    import re
    print("times found :", re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)", html)[:10])
    print("iso dates   :", sorted(set(re.findall(r"\d{4}-\d{2}-\d{2}", html)))[:12])
    browser.close()
PY
```

Expected, and what it means:

- **Times found is non-empty** → Strategy A works. Inspect the saved fixture for
  the date-strip and showtime markup and continue at Step 2A.
- **Times found is empty but ISO dates include a contiguous run starting at
  today** → use Strategy B, Step 2B.

- [ ] **Step 2A: Strategy A — write the failing test, then the adapter**

Build `tests/fixtures/premiere_day.html` from the smallest slice of the saved
fixture containing one date strip and one showtime group, then write
`tests/test_premiere_adapter.py` following `tests/test_scene_adapter.py` exactly:
one test per pure function (`parse_tab_dates`, `parse_showtimes`,
`parse_movies`), one asserting `site_id == "premiere"`, and one real-fixture
guard. Implement `src/pop_hunt/adapters/premiere.py` in the same shape as
`scene.py`, with `collect` clicking the cinema button first:

```python
page.get_by_role("button", name=target.cinema, exact=True).click()
page.wait_for_timeout(6_000)
```

Skip to Step 3.

- [ ] **Step 2B: Strategy B — dates only from the embedded payload**

The risk is picking up unrelated dates (other films' release dates). Guard
against it by keeping only the **contiguous run of dates starting at today** —
a booking window is by definition consecutive days from today.

```python
# tests/test_premiere_adapter.py
from datetime import date

from pop_hunt.adapters.premiere import PremiereAdapter, booking_window


def test_booking_window_keeps_the_contiguous_run_from_today():
    payload = ["2026-07-29", "2026-07-30", "2026-07-31", "2026-06-23", "2026-09-01"]
    assert booking_window(payload, today=date(2026, 7, 29)) == [
        "2026-07-29",
        "2026-07-30",
        "2026-07-31",
    ]


def test_booking_window_tolerates_a_window_starting_tomorrow():
    payload = ["2026-07-30", "2026-07-31"]
    assert booking_window(payload, today=date(2026, 7, 29)) == [
        "2026-07-30",
        "2026-07-31",
    ]


def test_booking_window_drops_past_dates():
    payload = ["2026-05-16", "2026-06-17"]
    assert booking_window(payload, today=date(2026, 7, 29)) == []


def test_booking_window_stops_at_the_first_gap():
    payload = ["2026-07-29", "2026-07-30", "2026-08-05"]
    assert booking_window(payload, today=date(2026, 7, 29)) == [
        "2026-07-29",
        "2026-07-30",
    ]


def test_adapter_declares_its_site_id():
    assert PremiereAdapter().site_id == "premiere"
```

Run: `.venv/bin/pytest tests/test_premiere_adapter.py -v` → expect FAIL, then implement:

```python
# src/pop_hunt/adapters/premiere.py
"""Premiere Cinemas (premiere-cinemas.com).

A Next.js SPA that renders nothing until a cinema is chosen. The booking window
is present in the embedded page payload, so the dates are read from there and
the window is reconstructed as the contiguous run of days from today.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from pop_hunt.config import Target
from pop_hunt.models import Snapshot

SITE_ID = "premiere"

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_payload_dates(html: str) -> list[str]:
    """Every ISO date appearing anywhere in the page, deduped and sorted."""
    return sorted(set(_ISO_DATE.findall(html)))


def booking_window(dates: list[str], today: date) -> list[str]:
    """The contiguous run of bookable days beginning today or tomorrow.

    The payload also carries unrelated dates (other films' release dates), so a
    plain max() would be wrong. A booking window is consecutive days, which is
    what makes this filter safe.
    """
    available = {d for d in dates if date.fromisoformat(d) >= today}
    if not available:
        return []
    start = today if today.isoformat() in available else today + timedelta(days=1)
    window: list[str] = []
    cursor = start
    while cursor.isoformat() in available:
        window.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return window


class PremiereAdapter:
    site_id = SITE_ID

    def collect(self, page, target: Target) -> Snapshot:
        if target.cinema:
            try:
                page.get_by_role(
                    "button", name=target.cinema, exact=True
                ).click(timeout=15_000)
                page.wait_for_timeout(6_000)
            except Exception:
                # Selecting the cinema is best-effort: the payload already
                # carries the booking window even when the UI does not render.
                pass
        dates = booking_window(parse_payload_dates(page.content()), date.today())
        return Snapshot(target_id=target.id, dates=dates, movies=[])
```

- [ ] **Step 3: Run the adapter tests and the registry test**

Run: `.venv/bin/pytest tests/test_premiere_adapter.py tests/test_adapter_registry.py -v`
Expected: PASS — including the registry test from Task 9, which has been red until now.

- [ ] **Step 4: Verify against the live site**

```bash
.venv/bin/python - <<'PY'
from pop_hunt.adapters import get_adapter
from pop_hunt.config import load_targets
from pop_hunt.fetcher import browser_context, collect_target

target = next(t for t in load_targets("targets.yaml") if t.site == "premiere")
with browser_context() as context:
    snap = collect_target(context, target, get_adapter("premiere"))
print("dates :", snap.dates)
print("movies:", [m.title for m in snap.movies])
PY
```

Expected: a contiguous run of ~7 dates starting today or tomorrow. If `dates` is
empty, the target will simply be reported `error` on the dashboard and never
alert — see "Known limitations".

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/adapters tests/test_premiere_adapter.py tests/fixtures
git commit -m "feat: add premiere cinemas adapter"
```

---

## Task 14: Fetcher

**Files:**
- Create: `src/pop_hunt/fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetcher.py
from pop_hunt.config import Target
from pop_hunt.fetcher import collect_target
from pop_hunt.models import Snapshot

TARGET = Target(id="t1", label="T", site="scene", url="https://x.test")


class _FakePage:
    def __init__(self):
        self.goto_calls = []
        self.closed = False

    def goto(self, url, wait_until, timeout):
        self.goto_calls.append(url)

    def wait_for_timeout(self, ms):
        pass

    def close(self):
        self.closed = True


class _FakeContext:
    def __init__(self, page):
        self._page = page

    def new_page(self):
        return self._page


class _FakeAdapter:
    site_id = "scene"

    def __init__(self):
        self.seen_page = None

    def collect(self, page, target):
        self.seen_page = page
        return Snapshot(target_id=target.id, dates=["2026-08-05"], movies=[])


def test_collect_target_navigates_and_delegates_to_the_adapter():
    page = _FakePage()
    adapter = _FakeAdapter()

    snapshot = collect_target(_FakeContext(page), TARGET, adapter)

    assert page.goto_calls == ["https://x.test"]
    assert adapter.seen_page is page
    assert snapshot.dates == ["2026-08-05"]


def test_collect_target_always_closes_the_page():
    page = _FakePage()
    collect_target(_FakeContext(page), TARGET, _FakeAdapter())
    assert page.closed is True


def test_collect_target_closes_the_page_even_when_the_adapter_raises():
    page = _FakePage()

    class Boom:
        site_id = "scene"

        def collect(self, page, target):
            raise RuntimeError("selector gone")

    try:
        collect_target(_FakeContext(page), TARGET, Boom())
    except RuntimeError:
        pass
    assert page.closed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.fetcher'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/fetcher.py
"""Playwright lifecycle. The only module that knows a browser exists."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from pop_hunt.config import Target
from pop_hunt.models import Snapshot

log = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 60_000
SETTLE_MS = 3_000
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


@contextmanager
def browser_context():
    """A headless Chromium context that looks like a normal desktop browser."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        try:
            yield context
        finally:
            context.close()
            browser.close()


def collect_target(context, target: Target, adapter) -> Snapshot:
    """Render one target and hand the page to its adapter."""
    page = context.new_page()
    try:
        log.info("rendering %s", target.id)
        page.goto(target.url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
        page.wait_for_timeout(SETTLE_MS)
        return adapter.collect(page, target)
    finally:
        page.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_fetcher.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/pop_hunt/fetcher.py tests/test_fetcher.py
git commit -m "feat: add playwright fetcher"
```

---

## Task 15: Orchestrator

Ties everything together. The tricky requirement: a target that fails to render must **keep its previous dashboard entry**, marked stale, rather than vanishing.

**Files:**
- Create: `src/pop_hunt/main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
from pop_hunt.config import Settings, Target
from pop_hunt.main import build_entry, carry_over, run_targets
from pop_hunt.models import Movie, Showtime, Snapshot

SETTINGS = Settings(telegram_bot_token=None, telegram_chat_id=None, tz="Africa/Cairo")
TARGET = Target(id="t1", label="T1", site="scene", url="https://x.test", scope="movie")

SNAPSHOT = Snapshot(
    target_id="t1",
    dates=["2026-08-05", "2026-08-06"],
    movies=[Movie(title="A", showtimes={"2026-08-05": [Showtime(time="2:00pm")]})],
)


def test_build_entry_exposes_what_the_dashboard_needs():
    entry = build_entry(TARGET, SNAPSHOT, status="ok")
    assert entry["id"] == "t1"
    assert entry["label"] == "T1"
    assert entry["url"] == "https://x.test"
    assert entry["dates"] == ["2026-08-05", "2026-08-06"]
    assert entry["status"] == "ok"
    assert entry["movies"][0]["title"] == "A"


def test_carry_over_marks_a_previous_entry_stale():
    previous = {"targets": [build_entry(TARGET, SNAPSHOT, status="ok")]}
    entry = carry_over(TARGET, previous, now="2026-08-01T10:00:00+03:00")
    assert entry["status"] == "stale"
    assert entry["stale_since"] == "2026-08-01T10:00:00+03:00"
    assert entry["movies"][0]["title"] == "A"


def test_carry_over_keeps_the_original_stale_since_on_repeat_failures():
    stale = build_entry(TARGET, SNAPSHOT, status="ok")
    stale["status"] = "stale"
    stale["stale_since"] = "2026-08-01T10:00:00+03:00"
    entry = carry_over(TARGET, {"targets": [stale]}, now="2026-08-01T11:00:00+03:00")
    assert entry["stale_since"] == "2026-08-01T10:00:00+03:00"


def test_carry_over_produces_an_error_entry_when_nothing_was_ever_captured():
    entry = carry_over(TARGET, {"targets": []}, now="2026-08-01T10:00:00+03:00")
    assert entry["status"] == "error"
    assert entry["movies"] == []
    assert entry["dates"] == []


def test_run_targets_alerts_only_when_a_new_day_opens():
    collected = {"t1": SNAPSHOT}
    state = {"t1": "2026-08-05"}
    entries, alerts, new_state = run_targets(
        [TARGET],
        state,
        {"targets": []},
        collect=lambda target: collected[target.id],
        now="2026-08-01T10:00:00+03:00",
    )
    assert [t.id for t, _ in alerts] == ["t1"]
    assert new_state["t1"] == "2026-08-06"
    assert entries[0]["status"] == "ok"


def test_run_targets_does_not_alert_on_first_ever_run():
    entries, alerts, new_state = run_targets(
        [TARGET],
        {},
        {"targets": []},
        collect=lambda target: SNAPSHOT,
        now="2026-08-01T10:00:00+03:00",
    )
    assert alerts == []
    assert new_state["t1"] == "2026-08-06"


def test_run_targets_carries_over_and_keeps_state_when_a_target_raises():
    previous = {"targets": [build_entry(TARGET, SNAPSHOT, status="ok")]}

    def boom(target):
        raise RuntimeError("render failed")

    entries, alerts, new_state = run_targets(
        [TARGET],
        {"t1": "2026-08-05"},
        previous,
        collect=boom,
        now="2026-08-01T10:00:00+03:00",
    )
    assert alerts == []
    assert new_state == {"t1": "2026-08-05"}
    assert entries[0]["status"] == "stale"


def test_run_targets_never_lets_state_go_backwards():
    shrunk = Snapshot(target_id="t1", dates=["2026-08-01"], movies=[])
    _, alerts, new_state = run_targets(
        [TARGET],
        {"t1": "2026-08-05"},
        {"targets": []},
        collect=lambda target: shrunk,
        now="2026-08-01T10:00:00+03:00",
    )
    assert alerts == []
    assert new_state["t1"] == "2026-08-05"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pop_hunt.main'`

- [ ] **Step 3: Write the implementation**

```python
# src/pop_hunt/main.py
"""One monitoring run: render every target, detect, alert, persist."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pop_hunt.adapters import get_adapter
from pop_hunt.config import Settings, Target, load_settings, load_targets
from pop_hunt.detector import NEW_DAY, NO_DATES, Detection, detect
from pop_hunt.fetcher import browser_context, collect_target
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
    """Reuse the last good entry so a failed render doesn't empty the dashboard."""
    for entry in previous.get("targets") or []:
        if entry.get("id") == target.id and entry.get("movies"):
            carried = dict(entry)
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
        "stale_since": now,
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

        # Never regress: a partial render must not re-arm an alert.
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

    with browser_context() as context:

        def collect(target: Target) -> Snapshot:
            return collect_target(context, target, get_adapter(target.site))

        entries, alerts, new_state = run_targets(
            targets, state, previous, collect, now
        )

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_main.py -v`
Expected: PASS — 8 passed

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -v`
Expected: PASS — every test green.

- [ ] **Step 6: Do a real end-to-end run**

Run: `.venv/bin/python -m pop_hunt.main`
Expected: log lines rendering each target, `run complete: 4 targets, 0 alerts` (first run is baseline, so no alerts), and `state.json` + `data/snapshot.json` created.

- [ ] **Step 7: Verify the baseline landed**

Run: `cat state.json`
Expected: one ISO date per target id, e.g. `{"vox-moe-spiderman": "2026-08-05", ...}`

- [ ] **Step 8: Commit**

```bash
git add src/pop_hunt/main.py tests/test_main.py state.json data
git commit -m "feat: add monitoring run orchestrator"
```

---

## Task 16: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/monitor.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/monitor.yml
name: monitor

on:
  schedule:
    - cron: "*/30 * * * *"
  workflow_dispatch:

concurrency:
  group: monitor
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -e .
          python -m playwright install --with-deps chromium

      - name: Run monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          CHECK_TZ: Africa/Cairo
        run: python -m pop_hunt.main

      - name: Commit data if it changed
        run: |
          git config user.name "pop-hunt bot"
          git config user.email "actions@github.com"
          git add state.json data
          if git diff --cached --quiet; then
            echo "no data change"
          else
            git commit -m "data: update booking state [skip ci]"
            git push
          fi
```

- [ ] **Step 2: Validate the YAML parses**

Run: `.venv/bin/python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/monitor.yml').read_text()); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/monitor.yml
git commit -m "ci: run the monitor every 30 minutes"
```

---

## Task 17: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write it**

````markdown
# pop-hunt

Alerts you on Telegram when a tracked cinema opens a **new bookable day**.

Egyptian cinemas sell tickets on a rolling window (~7 days). When the furthest
bookable date moves forward, a new day has opened — that is what this watches.

## How it works

Every 30 minutes a GitHub Actions job renders each URL in `targets.yaml` with
headless Chromium, extracts the dates that have showtimes, and compares the
furthest one to the last-seen value in `state.json`. If it advanced, you get a
Telegram message. Each run also writes `data/snapshot.json` (what's showing) and
`data/events.json` (a log of openings) for the dashboard.

## Setup

### 1. Telegram

1. Message [@BotFather](https://t.me/BotFather) and send `/newbot`; follow the
   prompts and copy the token it gives you.
2. Send your new bot any message (it cannot message you first).
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and copy
   `result[0].message.chat.id`.

### 2. GitHub

Add these as **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | the BotFather token |
| `TELEGRAM_CHAT_ID` | the chat id from step 3 |

Then run the **monitor** workflow manually once (Actions → monitor → Run
workflow) to confirm it works. The first run records a baseline and sends no
alert — that is expected.

## Adding a target

Edit `targets.yaml`:

```yaml
  - id: vox-moe-spiderman            # unique
    label: "VOX Mall of Egypt — Spider-Man"
    site: vox                        # vox | scene | premiere
    scope: movie                     # movie | cinema
    url: "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man-brand-new-day"
```

A new target records a baseline on its first run, then alerts from the next
opening onwards.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install --with-deps chromium
.venv/bin/pytest                       # tests never touch the network
.venv/bin/python -m pop_hunt.main      # a real run
```

### When a cinema redesigns its site

Adapter tests run against saved HTML in `tests/fixtures/`. Refresh it with:

```bash
.venv/bin/python scripts/capture_fixtures.py <target_id>
```

Then update the selectors in `src/pop_hunt/adapters/<site>.py` until the tests
pass again.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add setup and development guide"
```

---

## Task 18: Final verification

- [ ] **Step 1: Full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass, no skips.

- [ ] **Step 2: Confirm no network in tests**

Run: `.venv/bin/pytest -p no:cacheprovider -q`
Expected: completes in a few seconds — proof nothing is hitting a real site.

- [ ] **Step 3: Second real run detects no change**

Run: `.venv/bin/python -m pop_hunt.main`
Expected: `run complete: 4 targets, 0 alerts`, and `git status` shows
`state.json` / `data/snapshot.json` unchanged (write-if-changed working).

- [ ] **Step 4: Prove an alert fires**

Temporarily rewind one target's stored date, then run:

```bash
.venv/bin/python -c "
import json
s = json.load(open('state.json'))
key = sorted(s)[0]
s[key] = '2020-01-01'
json.dump(s, open('state.json','w'), indent=2)
print('rewound', key)
"
.venv/bin/python -m pop_hunt.main
```

Expected: `run complete: 4 targets, 1 alerts`. With Telegram secrets exported
you receive a message; without them the log shows
`Telegram is not configured; skipping alert:` followed by the message text.

- [ ] **Step 5: Restore real state**

Run: `.venv/bin/python -m pop_hunt.main`
Expected: `0 alerts` again. Confirm `data/events.json` contains the test event,
then delete that entry before committing.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: verify phase 1 end to end"
```

---

## Known limitations

Accepted for Phase 1, recorded so they are not mistaken for bugs:

- **Cinema-scope showtimes are not split per movie.** For a `scope: cinema`
  target, every movie on the page carries the same `showtimes_by_date` map.
  Detection is exact regardless (it only uses the date set); only the
  dashboard's per-movie breakdown is coarse. Fix by parsing showtimes inside
  each `<article>` rather than page-wide.
- **Premiere may yield dates only, or nothing.** Its SPA did not render
  showtimes on demand during investigation. Strategy B (Task 13) recovers the
  booking window without movies, and a total failure degrades to an `error`
  entry for that one target — the other three keep working.
- **Regex parsing, not a DOM parser.** Chosen so the pure functions are
  testable with no browser. It is tolerant enough for these three sites but
  will need updating after a redesign; the real-fixture guard test in each
  adapter is what catches that.

## Done when

- `pytest` is green and touches no network.
- A real run writes `state.json` and `data/snapshot.json`, and a second run
  changes neither file.
- Rewinding a stored date produces exactly one alert.
- The workflow is committed and a manual `workflow_dispatch` run succeeds.

**Next:** Phase 2 — the Vite + React 19 + TanStack Router dashboard on
Cloudflare Pages, consuming `data/snapshot.json` and `data/events.json`.
