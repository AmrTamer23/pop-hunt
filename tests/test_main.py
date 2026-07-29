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


def test_carry_over_does_not_mutate_the_previous_entry():
    original = build_entry(TARGET, SNAPSHOT, status="ok")
    previous = {"targets": [original]}
    carry_over(TARGET, previous, now="2026-08-01T10:00:00+03:00")
    assert original["status"] == "ok"
    assert "stale_since" not in original


def test_run_targets_alerts_only_when_a_new_day_opens():
    entries, alerts, new_state = run_targets(
        [TARGET],
        {"t1": "2026-08-05"},
        {"targets": []},
        collect=lambda target: SNAPSHOT,
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


def test_run_targets_carries_over_when_a_target_yields_no_dates():
    previous = {"targets": [build_entry(TARGET, SNAPSHOT, status="ok")]}
    empty = Snapshot(target_id="t1", dates=[], movies=[])

    entries, alerts, new_state = run_targets(
        [TARGET],
        {"t1": "2026-08-05"},
        previous,
        collect=lambda target: empty,
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


def test_run_targets_keeps_going_after_one_target_fails():
    other = Target(id="t2", label="T2", site="scene", url="https://y.test")

    def collect(target):
        if target.id == "t1":
            raise RuntimeError("render failed")
        return Snapshot(target_id="t2", dates=["2026-08-09"], movies=[])

    entries, alerts, new_state = run_targets(
        [TARGET, other],
        {"t1": "2026-08-05", "t2": "2026-08-08"},
        {"targets": []},
        collect=collect,
        now="2026-08-01T10:00:00+03:00",
    )
    assert [e["id"] for e in entries] == ["t1", "t2"]
    assert [t.id for t, _ in alerts] == ["t2"]
    assert new_state["t2"] == "2026-08-09"
