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

# NOTE the `amp;`: raw HTML separates query params with `&amp;`, so matching
# only `[?&]d=` finds ZERO dates and the adapter would never alert.
_DATE_PARAM = re.compile(r"[?&](?:amp;)?d=(\d{8})")
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
            inner_text = _text(inner)
            time_match = _TIME_TEXT.search(inner_text)
            if not time_match:
                continue
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


def parse_movies_with_showtimes(html: str, iso_date: str) -> list[Movie]:
    """One Movie per article, each carrying only ITS OWN showtimes.

    VOX groups showtimes inside each <article class="movie-compare">, so the
    per-article fragment is the correct scope. Parsing page-wide instead gives
    every movie the whole cinema's schedule - invisible to detection, which
    only reads dates, but plainly wrong on the dashboard.
    """
    movies: list[Movie] = []
    for article in _ARTICLE.findall(html):
        parsed = parse_movies(article)
        if not parsed:
            continue
        showtimes = parse_showtimes(article)
        movie = parsed[0]
        movies.append(
            Movie(
                title=movie.title,
                poster_url=movie.poster_url,
                rating=movie.rating,
                runtime_min=movie.runtime_min,
                language=movie.language,
                showtimes={iso_date: showtimes} if showtimes else {},
            )
        )
    return movies


class VoxAdapter:
    site_id = SITE_ID

    def collect(self, page, target: Target) -> Snapshot:
        """Read everything off the page the fetcher already loaded.

        DO NOT ADD NAVIGATION HERE. VOX rejects the second request made from a
        reused context with net::ERR_HTTP2_PROTOCOL_ERROR, so a per-date
        `page.goto` loop fails every VOX run outright - it is what this method
        used to do, and it took both VOX targets down.

        It is also unnecessary for detection: the date strip is specific to
        this movie at this cinema, so a date appearing in the strip already
        means the movie has showings that day. Phase 1 therefore records
        showtimes only for the day the page rendered, and defers per-day
        showtimes for the remaining dates to Phase 2 - which will need a FRESH
        CONTEXT per date. `date_url` is kept for exactly that.
        """
        html = page.content()
        link_dates = parse_date_links(html)

        dates: list[str] = list(link_dates)
        movies = parse_movies(html)

        # The displayed day is not in the strip - it renders as Today/Tomorrow -
        # so it precedes the first link. It is also the one day whose showtimes
        # we can actually see, so it counts only if it has at least one, keeping
        # the "a date counts only if it has >=1 showtime" rule intact where it
        # is observable.
        if link_dates and parse_showtimes(html):
            displayed = preceding_day(link_dates[0])
            dates.append(displayed)
            # Per article, never page-wide: a cinema-scope target lists every
            # movie at that cinema, and each must carry only its own times.
            movies = parse_movies_with_showtimes(html, displayed)

        return Snapshot(
            target_id=target.id,
            dates=sorted(dates),
            movies=movies,
        )
