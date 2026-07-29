from datetime import date
from pathlib import Path

from pop_hunt.adapters.premiere import (
    PremiereAdapter,
    parse_chooser_options,
    parse_movie_meta,
    parse_payload_dates,
    parse_strip_dates,
    parse_time_options,
)
from pop_hunt.config import Target

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_HTML = (FIXTURES / "premiere-cima-arkan-spiderman.html").read_text()
DAY_HTML = (FIXTURES / "premiere_day.html").read_text()

# premiere_day.html was captured on this date, after driving the wizard to
# Cima Arkan -> 30 Jul -> 2D -> Standard. The strip carries no year, so the
# expected ISO dates only hold relative to the day of capture.
CAPTURED_ON = date(2026, 7, 29)

TARGET = Target(
    id="premiere-cima-arkan-spiderman",
    label="Premiere Cima Arkan — Spider-Man: Brand New Day",
    site="premiere",
    url="https://www.premiere-cinemas.com/en/movie-details/9961.764/1",
    cinema="Cima Arkan",
)


class FakeLocator:
    def __init__(self, page, label, count):
        self._page, self._label, self._count = page, label, count

    def count(self):
        return self._count

    @property
    def first(self):
        return self

    def nth(self, index):
        return FakeLocator(self._page, f"{self._label}#{index}", self._count)

    def click(self):
        if self._count == 0:
            raise AssertionError(f"clicked a locator that matches nothing: {self._label}")
        self._page.clicked.append(self._label)


class FakePage:
    """Enough of the Playwright page API to drive the adapter.

    Serves `before` until something is clicked and `after` from then on,
    which is how the real SPA behaves: the strip, formats, experiences and
    times all appear only once a cinema is chosen.
    """

    def __init__(self, before, after=None):
        self.before, self.after = before, after if after is not None else before
        self.clicked: list[str] = []

    def content(self):
        return self.after if self.clicked else self.before

    def wait_for_timeout(self, milliseconds):
        pass

    def get_by_role(self, role, name, exact=False):
        present = f">{name}</button>" in self.content()
        return FakeLocator(self, name, 1 if present else 0)

    def locator(self, selector):
        return FakeLocator(self, selector, self.content().count("dates-container"))


def test_parse_strip_dates_reads_the_rendered_date_strip():
    assert parse_strip_dates(DAY_HTML, CAPTURED_ON) == [
        "2026-07-30",
        "2026-07-31",
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
    ]


def test_parse_strip_dates_zero_pads_single_digit_days():
    cell = "<div><p>Sat</p><p>1</p><p>Aug</p></div>"
    assert parse_strip_dates(cell, date(2026, 7, 29)) == ["2026-08-01"]


def test_parse_strip_dates_rolls_the_year_over_at_new_year():
    cell = "<div><p>Fri</p><p>02</p><p>Jan</p></div>"
    assert parse_strip_dates(cell, date(2026, 12, 30)) == ["2027-01-02"]


def test_parse_strip_dates_is_empty_before_a_cinema_is_selected():
    # The SPA renders no strip at all until a cinema is chosen.
    assert parse_strip_dates(PAGE_HTML, CAPTURED_ON) == []


def test_parse_payload_dates_reads_the_embedded_show_dates():
    assert parse_payload_dates(PAGE_HTML) == [
        "2026-07-29",
        "2026-07-30",
        "2026-07-31",
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
    ]


def test_parse_payload_dates_is_empty_without_a_flight_payload():
    assert parse_payload_dates("<html><body>nothing</body></html>") == []


def test_parse_movie_meta_reads_title_poster_rating_runtime_and_language():
    movie = parse_movie_meta(PAGE_HTML)
    assert movie.title == "Spider-Man: Brand New Day"
    assert movie.poster_url == (
        "https://mifcentral-api.premiere-cinemas.com"
        "/uploads/gallery/1784721368952-website_showing_now_banner_640x903.jpg"
    )
    assert movie.rating == "+12"
    assert movie.runtime_min == 145
    assert movie.language == "English"


def test_parse_movie_meta_falls_back_when_the_payload_is_missing():
    movie = parse_movie_meta("<html></html>")
    assert movie.title == "Unknown"
    assert movie.poster_url is None


def test_parse_chooser_options_lists_the_cinema_buttons_by_heading_text():
    assert parse_chooser_options(PAGE_HTML, "CHOOSE YOUR CINEMA") == [
        "Nile Cinema",
        "Premiere Plaza",
        "Galaxy elManial",
        "Premiere Point90",
        "Cima Arkan",
    ]


def test_parse_chooser_options_stops_at_the_end_of_the_button_row():
    html = (
        "<p>Choose Formats</p></div>"
        "<div><button>2D</button><button>3D</button></div>"
        "<div>elsewhere<button>BOOK TICKETS</button></div>"
    )
    assert parse_chooser_options(html, "Choose Formats") == ["2D", "3D"]


def test_parse_chooser_options_stops_at_the_next_heading():
    html = "<p>Choose Formats</p><p>Choose Experience</p><button>MAX</button>"
    assert parse_chooser_options(html, "Choose Formats") == []


def test_parse_chooser_options_is_empty_when_the_heading_is_absent():
    assert parse_chooser_options("<div><button>2D</button></div>", "Choose Formats") == []


def test_parse_time_options_reads_the_time_buttons():
    assert parse_time_options(DAY_HTML) == [
        "11:00 AM",
        "02:00 PM",
        "05:00 PM",
        "05:30 PM",
        "08:00 PM",
        "09:15 PM",
        "11:00 PM",
        "12:15 AM",
        "02:00 AM",
    ]


def test_parse_time_options_ignores_buttons_that_are_not_times():
    html = "<button>Standard</button><button>08:00 PM</button><button>BOOK</button>"
    assert parse_time_options(html) == ["08:00 PM"]


def test_adapter_declares_its_site_id():
    assert PremiereAdapter().site_id == "premiere"


def test_collect_selects_the_cinema_by_its_text():
    page = FakePage(PAGE_HTML, DAY_HTML)
    PremiereAdapter().collect(page, TARGET)
    assert page.clicked[0] == "Cima Arkan"


def test_collect_returns_the_strip_dates_sorted_and_zero_padded():
    page = FakePage(PAGE_HTML, DAY_HTML)
    snapshot = PremiereAdapter().collect(page, TARGET)
    assert snapshot.target_id == TARGET.id
    assert snapshot.dates == sorted(snapshot.dates)
    assert all(len(d) == 10 and d[4] == d[7] == "-" for d in snapshot.dates)
    assert snapshot.dates[0] == "2026-07-30"
    assert snapshot.dates[-1] == "2026-08-05"


def test_collect_reports_the_strip_not_the_wider_payload_window():
    # The payload's show_dates start a day earlier than this cinema's strip.
    page = FakePage(PAGE_HTML, DAY_HTML)
    snapshot = PremiereAdapter().collect(page, TARGET)
    assert "2026-07-29" in parse_payload_dates(PAGE_HTML)
    assert "2026-07-29" not in snapshot.dates


def test_collect_returns_showtimes_tagged_with_their_experience():
    page = FakePage(PAGE_HTML, DAY_HTML)
    snapshot = PremiereAdapter().collect(page, TARGET)
    movie = snapshot.movies[0]
    assert movie.title == "Spider-Man: Brand New Day"
    showtimes = movie.showtimes["2026-07-30"]
    assert showtimes[0].time == "11:00 AM"
    assert {s.experience for s in showtimes} == {"MAX", "Standard"}
    assert ("3D",) in {s.attributes for s in showtimes}


def test_collect_returns_no_dates_when_the_cinema_button_is_missing():
    # Premiere renames the cinema: the button the target names is gone.
    renamed = PAGE_HTML.replace(">Cima Arkan</button>", ">Arkan Mall</button>")
    page = FakePage(renamed, DAY_HTML)
    snapshot = PremiereAdapter().collect(page, TARGET)
    assert page.clicked == []
    # The payload window is right there and is deliberately NOT used: it is
    # the similar movies' site-wide window and can run ahead of this cinema.
    assert parse_payload_dates(renamed) != []
    assert snapshot.dates == []
    assert snapshot.movies == []


def test_collect_returns_no_dates_when_the_target_names_no_cinema():
    page = FakePage(PAGE_HTML, DAY_HTML)
    snapshot = PremiereAdapter().collect(page, Target(**{**vars(TARGET), "cinema": None}))
    assert page.clicked == []
    assert snapshot.dates == []
    assert snapshot.movies == []


def test_collect_returns_no_dates_when_the_strip_never_renders():
    # The cinema is selectable, but the strip behind it never paints.
    page = FakePage(PAGE_HTML)
    snapshot = PremiereAdapter().collect(page, TARGET)
    assert page.clicked == ["Cima Arkan"]
    assert snapshot.dates == []
    assert snapshot.movies == []


def test_collect_returns_no_dates_rather_than_raising_when_nothing_is_there():
    page = FakePage("<html><body>redesigned</body></html>")
    snapshot = PremiereAdapter().collect(page, TARGET)
    assert snapshot.target_id == TARGET.id
    assert snapshot.dates == []
    assert snapshot.movies == []


def test_real_fixture_still_exposes_the_chooser_payload_and_metadata():
    """Guards against a site redesign silently breaking the selectors."""
    assert "Cima Arkan" in parse_chooser_options(PAGE_HTML, "CHOOSE YOUR CINEMA")
    assert len(parse_payload_dates(PAGE_HTML)) >= 1
    assert parse_movie_meta(PAGE_HTML).title == "Spider-Man: Brand New Day"


def test_real_day_fixture_still_yields_the_strip_formats_and_times():
    """Guards the post-selection wizard: strip, formats, experiences, times."""
    assert len(parse_strip_dates(DAY_HTML, CAPTURED_ON)) == 7
    assert parse_chooser_options(DAY_HTML, "Choose Formats") == ["2D", "3D"]
    assert parse_chooser_options(DAY_HTML, "Choose Experience") == ["MAX", "Standard"]
    assert len(parse_time_options(DAY_HTML)) == 9
    # collect() reads metadata from the post-selection page, so the payload
    # has to survive the wizard rerenders too.
    assert parse_movie_meta(DAY_HTML).title == "Spider-Man: Brand New Day"
