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


def test_parse_date_links_handles_html_escaped_separators():
    # Raw HTML uses &amp;d=, not &d=. Matching only [?&]d= finds nothing.
    assert parse_date_links('<a href="/s?c=x&amp;d=20260806">x</a>') == ["2026-08-06"]


def test_parse_date_links_is_empty_when_no_strip_present():
    assert parse_date_links("<div>nothing</div>") == []


def test_preceding_day_recovers_the_selected_day():
    assert preceding_day("2026-07-31") == "2026-07-30"
    assert preceding_day("2026-01-01") == "2025-12-31"


def test_date_url_sets_the_d_param_without_duplicating_it():
    base = "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man"
    assert date_url(base, "2026-08-01").endswith("d=20260801")
    result = date_url(base + "&d=20260731", "2026-08-01")
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


def test_real_fixture_still_yields_dates_showtimes_and_movies():
    html = (FIXTURES / "vox-moe-spiderman.html").read_text()
    assert len(parse_date_links(html)) >= 1
    assert len(parse_showtimes(html)) >= 1
    assert len(parse_movies(html)) >= 1
