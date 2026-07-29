from pathlib import Path

from pop_hunt.adapters.vox import (
    VoxAdapter,
    date_url,
    parse_date_links,
    parse_movies,
    parse_movies_with_showtimes,
    parse_showtimes,
    preceding_day,
)
from pop_hunt.config import Target

FIXTURES = Path(__file__).parent / "fixtures"
DAY_HTML = (FIXTURES / "vox_day.html").read_text()

TARGET = Target(
    id="vox-1",
    label="VOX",
    site="vox",
    url="https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man",
)


class _FakePage:
    """A page that fails loudly if `collect` tries to drive the browser.

    Only `content()` is provided: any other call raises AttributeError, so a
    reintroduced navigation loop cannot pass silently.
    """

    def __init__(self, html: str):
        self._html = html
        self.goto_calls = 0

    def content(self) -> str:
        return self._html

    def goto(self, *args, **kwargs):
        self.goto_calls += 1
        raise AssertionError("collect must not navigate")


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


def test_parse_movies_with_showtimes_attributes_times_to_their_own_movie():
    html = (FIXTURES / "vox_two_movies.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")

    by_title = {m.title: m for m in movies}
    assert set(by_title) == {"Spider-Man: Brand New Day", "The Odyssey"}

    spidey = by_title["Spider-Man: Brand New Day"].showtimes["2026-07-30"]
    odyssey = by_title["The Odyssey"].showtimes["2026-07-30"]

    assert [s.time for s in spidey] == ["10:45am", "2:00pm", "12:00pm", "1:30pm"]
    assert [s.time for s in odyssey] == ["6:00pm", "9:30pm"]
    # The bug this guards: every movie carrying every movie's times.
    assert all(s.time not in {"6:00pm", "9:30pm"} for s in spidey)


def test_parse_movies_with_showtimes_keeps_movie_metadata():
    html = (FIXTURES / "vox_two_movies.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")
    spidey = next(m for m in movies if m.title == "Spider-Man: Brand New Day")
    assert spidey.rating == "12+"
    assert spidey.runtime_min == 140
    assert spidey.language == "English"
    assert spidey.poster_url is not None


def test_real_cinema_fixture_gives_each_movie_its_own_showtimes():
    """vox-moe-all has 17 movies; they must not all share one schedule."""
    html = (FIXTURES / "vox-moe-all.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")
    assert len(movies) >= 10
    schedules = [
        tuple((s.time, s.experience) for s in m.showtimes.get("2026-07-30", []))
        for m in movies
    ]
    assert len(set(schedules)) > 1, "every movie got an identical schedule"


def test_adapter_declares_its_site_id():
    assert VoxAdapter().site_id == "vox"


def test_real_fixture_still_yields_dates_showtimes_and_movies():
    html = (FIXTURES / "vox-moe-spiderman.html").read_text()
    assert len(parse_date_links(html)) >= 1
    assert len(parse_showtimes(html)) >= 1
    assert len(parse_movies(html)) >= 1


def test_collect_returns_the_link_dates_plus_the_displayed_day_sorted():
    snapshot = VoxAdapter().collect(_FakePage(DAY_HTML), TARGET)
    assert snapshot.dates == ["2026-07-30", "2026-07-31", "2026-08-01"]
    assert snapshot.target_id == "vox-1"


def test_collect_never_navigates():
    """VOX rejects the second request from a reused context; the strip is enough."""
    # _FakePage.goto raises, so this passing proves no navigation happened.
    assert VoxAdapter().collect(_FakePage(DAY_HTML), TARGET).dates


def test_collect_records_showtimes_for_the_displayed_day_only():
    snapshot = VoxAdapter().collect(_FakePage(DAY_HTML), TARGET)
    movie = snapshot.movies[0]
    assert movie.title == "Spider-Man: Brand New Day"
    assert list(movie.showtimes) == ["2026-07-30"]
    assert [s.time for s in movie.showtimes["2026-07-30"]] == [
        "10:45am",
        "2:00pm",
        "12:00pm",
        "1:30pm",
    ]


def test_collect_gives_each_movie_its_own_showtimes_without_navigating():
    """A cinema-scope page must not hand every movie the whole schedule."""
    page = _FakePage((FIXTURES / "vox_two_movies.html").read_text())
    snapshot = VoxAdapter().collect(page, TARGET)

    by_title = {m.title: m for m in snapshot.movies}
    assert set(by_title) == {"Spider-Man: Brand New Day", "The Odyssey"}
    assert [s.time for s in by_title["Spider-Man: Brand New Day"].showtimes["2026-07-30"]] == [
        "10:45am",
        "2:00pm",
        "12:00pm",
        "1:30pm",
    ]
    assert [s.time for s in by_title["The Odyssey"].showtimes["2026-07-30"]] == [
        "6:00pm",
        "9:30pm",
    ]
    # _FakePage.goto raises, so reaching here already proves it; assert anyway.
    assert page.goto_calls == 0


def test_collect_without_a_date_strip_yields_no_dates_and_does_not_raise():
    snapshot = VoxAdapter().collect(_FakePage("<div>nothing</div>"), TARGET)
    assert snapshot.dates == []


def test_collect_omits_the_displayed_day_when_it_has_no_showtimes():
    """The displayed day is the one day we can verify, so the rule still applies."""
    html = '<a href="/s?c=x&amp;d=20260731">x</a>'
    snapshot = VoxAdapter().collect(_FakePage(html), TARGET)
    assert snapshot.dates == ["2026-07-31"]
