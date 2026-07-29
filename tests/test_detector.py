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


def test_new_day_dedupes_repeated_dates_in_added():
    # Responsive sites often render the date strip twice (desktop + mobile DOM).
    result = detect("2026-08-05", ["2026-08-06", "2026-08-06"])
    assert result.added == ["2026-08-06"]


def test_new_day_handles_unsorted_input():
    result = detect("2026-08-05", ["2026-08-08", "2026-08-06"])
    assert result.new_max == "2026-08-08"
    assert result.added == ["2026-08-06", "2026-08-08"]
