"""Scene Cinemas (scenecinemas.com).

Dates are tabs that call the page function LoadShowtimes('DD-MM-YYYY');
showtimes for the selected date render into div.showtimes, grouped into
experience blocks (Premiere, Standard & Deluxe).
"""

from __future__ import annotations

import re
from html import unescape

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
