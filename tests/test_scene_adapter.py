from pathlib import Path

from pop_hunt.adapters.scene import SceneAdapter, parse_showtimes, parse_tab_dates

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
