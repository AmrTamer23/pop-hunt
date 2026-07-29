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
