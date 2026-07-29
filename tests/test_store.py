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
