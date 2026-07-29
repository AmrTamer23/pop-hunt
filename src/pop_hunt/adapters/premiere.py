"""Premiere Cinemas (premiere-cinemas.com).

A Next.js SPA that ships no dates in its initial HTML - it renders "Invalid
Date" and a CHOOSE YOUR CINEMA row. Picking a cinema fires
`get-movie-show-dates/<movie>?...&cinema_id=<n>` and paints the date strip;
showtimes sit two wizard steps deeper still, behind a format then an
experience. So this adapter drives four levels of UI rather than one.

The cinema buttons carry nothing but generated utility classes, so they are
matched on their text - `target.cinema`. If that fails the target reports no
dates at all, deliberately: see `PremiereAdapter.collect`.

Movie metadata comes from the embedded Next.js payload, which streams
through `self.__next_f` rather than a classic `__NEXT_DATA__` blob.
"""

from __future__ import annotations

import json
import re
from datetime import date
from html import unescape

from pop_hunt.config import Target
from pop_hunt.dates import parse_day_month
from pop_hunt.models import Movie, Showtime, Snapshot

SITE_ID = "premiere"

# Posters in the payload are paths on the API host, not the www host.
MEDIA_BASE = "https://mifcentral-api.premiere-cinemas.com"

CINEMA_HEADING = "CHOOSE YOUR CINEMA"
FORMAT_HEADING = "Choose Formats"
EXPERIENCE_HEADING = "Choose Experience"

# The strip cells are the only element the site names semantically rather
# than with utility classes, so they are safe to click by selector.
DATE_CELL = "div.dates-container"

# Every wizard click goes through the API, so each one needs a settle wait.
SETTLE_MS = 1_500

# Bounded by `)</script>` because the chunk itself is full of brackets and
# quotes; json.loads then validates whatever was captured.
_PUSH = re.compile(r"self\.__next_f\.push\((.*?)\)</script>", re.DOTALL)

_SHOW_DATES = re.compile(r'"show_dates"\s*:\s*"([0-9,\-]*)"')
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

# A strip cell is three <p>: weekday, day-of-month, month. Matching that
# shape rather than the class keeps working when the utility classes churn
# (the selected cell already carries a longer class list than the rest).
_STRIP_CELL = re.compile(
    r"<div\b[^>]*>\s*<p\b[^>]*>\s*[A-Za-z]{3}\s*</p>\s*"
    r"<p\b[^>]*>\s*(\d{1,2})\s*</p>\s*"
    r"<p\b[^>]*>\s*([A-Za-z]{3})\s*</p>\s*</div>"
)

_BUTTON = re.compile(r"<button\b[^>]*>([^<]*)</button>")
_TIME_BUTTON = re.compile(
    r"<button\b[^>]*>\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*</button>", re.IGNORECASE
)
_HEADING = re.compile(r"(?:CHOOSE|Choose)\s[^<]*</p>")
_TAGS = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return unescape(_TAGS.sub(" ", fragment)).strip()


def decode_flight(html: str) -> str:
    """The streamed Next.js payload, reassembled into one JSON-ish string.

    Premiere pushes its data through `self.__next_f.push([1, "<chunk>"])`
    instead of a single blob, so the chunks have to be JSON-decoded and
    concatenated before anything can be read out of them.
    """
    chunks: list[str] = []
    for raw in _PUSH.findall(html):
        try:
            parts = json.loads(raw)
        except ValueError:
            continue
        if len(parts) > 1 and isinstance(parts[1], str):
            chunks.append(parts[1])
    return "".join(chunks)


def _json_object_after(text: str, key: str) -> dict:
    """The JSON object following `key`, found by brace matching.

    The payload is one long stream rather than a document, so the object has
    to be sliced out by counting braces (string-aware, or a `{` inside a
    movie plot would throw the count off).
    """
    marker = text.find(key)
    if marker == -1:
        return {}
    start = text.find("{", marker + len(key))
    if start == -1:
        return {}
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except ValueError:
                    return {}
    return {}


def parse_movie_meta(html: str) -> Movie:
    """Title, poster, rating, runtime and language from the embedded payload."""
    data = _json_object_after(decode_flight(html), '"movieDetailsData"')
    ratings = data.get("movie_ratings") or []
    artwork = data.get("movie_original_artwork") or ""
    return Movie(
        title=data.get("movie_title") or "Unknown",
        poster_url=f"{MEDIA_BASE}{artwork}" if artwork.startswith("/") else None,
        rating=ratings[0].get("rating") if ratings else None,
        runtime_min=data.get("movie_runtime") or None,
        language=data.get("movie_lang_name") or None,
    )


def parse_payload_dates(html: str) -> list[str]:
    """The site-wide booking window advertised in the embedded payload.

    Deliberately NOT a date source for detection - see the comment in
    `PremiereAdapter.collect` for why. These `show_dates` belong to the
    page's *similar movies*, so they describe what Premiere is selling
    across its cinemas, not what this cinema is selling for this film.

    Kept as a pure read of the payload: it is the only thing that can say
    what window the page advertises when the chooser cannot be driven,
    which makes it useful for the dashboard and for diagnosis.
    """
    dates: set[str] = set()
    for run in _SHOW_DATES.findall(decode_flight(html)):
        dates.update(d for d in run.split(",") if _ISO_DATE.fullmatch(d))
    return sorted(dates)


def parse_strip_dates(html: str, today: date) -> list[str]:
    """The rendered date strip, in document order.

    One entry per cell, deliberately not deduplicated: `collect` clicks the
    cells by position, so the list has to stay index-aligned with the DOM.
    The strip carries no year, so `today` supplies it (and the Dec -> Jan
    rollover) via `dates.parse_day_month`.
    """
    dates: list[str] = []
    for day, month in _STRIP_CELL.findall(html):
        try:
            dates.append(parse_day_month(f"{day} {month}", today))
        except ValueError:
            continue
    return dates


def parse_chooser_options(html: str, heading: str) -> list[str]:
    """Button labels in the chooser row introduced by `heading`.

    The buttons carry only generated utility classes, so the row is located
    by its heading text and bounded two ways: it ends at the next chooser
    heading, and at the first gap between one `</button>` and the next
    `<button>` - the buttons in a row are rendered as adjacent siblings.
    """
    anchor = re.search(re.escape(heading) + r"\s*</p>", html)
    if anchor is None:
        return []
    following = _HEADING.search(html, anchor.end())
    limit = following.start() if following else len(html)

    options: list[str] = []
    cursor = anchor.end()
    for match in _BUTTON.finditer(html, cursor):
        if match.start() >= limit:
            break
        if options and html[cursor : match.start()].strip():
            break
        cursor = match.end()
        label = _text(match.group(1))
        if label:
            options.append(label)
    return options


def parse_time_options(html: str) -> list[str]:
    """Every screening time currently offered, in document order."""
    return [" ".join(t.split()) for t in _TIME_BUTTON.findall(html)]


def _select_cinema(page, cinema: str | None) -> bool:
    """Click the cinema button by its text. False if it is not selectable.

    A renamed or removed button must not abort the run - the caller falls
    back to the payload window - so every failure mode here is swallowed.
    """
    if not cinema:
        return False
    try:
        button = page.get_by_role("button", name=cinema, exact=True)
        if button.count() == 0:
            return False
        button.first.click()
        return True
    except Exception:  # noqa: BLE001 - a chooser change must not break the run
        return False


def _showtimes_for_selected_date(page):
    """Walk format x experience for the date already selected."""
    for fmt in parse_chooser_options(page.content(), FORMAT_HEADING):
        page.get_by_role("button", name=fmt, exact=True).first.click()
        page.wait_for_timeout(SETTLE_MS)
        # 2D is the default, so only the marked formats are worth recording.
        attributes = () if fmt.upper() == "2D" else (fmt,)
        for experience in parse_chooser_options(page.content(), EXPERIENCE_HEADING):
            page.get_by_role("button", name=experience, exact=True).first.click()
            page.wait_for_timeout(SETTLE_MS)
            for time in parse_time_options(page.content()):
                yield Showtime(time=time, experience=experience, attributes=attributes)


def _collect_showtimes(page, strip: list[str]) -> dict[str, list[Showtime]]:
    """Drive the date -> format -> experience wizard, one leaf at a time."""
    found: dict[str, list[Showtime]] = {}
    cells = page.locator(DATE_CELL)
    for index, iso in enumerate(strip):
        if index >= cells.count():
            break
        try:
            cells.nth(index).click()
            page.wait_for_timeout(SETTLE_MS)
            for showtime in _showtimes_for_selected_date(page):
                found.setdefault(iso, []).append(showtime)
        except Exception:  # noqa: BLE001 - one bad day must not lose the rest
            continue
    return found


class PremiereAdapter:
    site_id = SITE_ID

    def collect(self, page, target: Target) -> Snapshot:
        # If the chooser cannot be driven, report nothing - never the payload
        # window from `parse_payload_dates`. Those dates belong to the page's
        # similar movies and can run ahead of this cinema's, and upstream
        # state never regresses (it keeps max(stored, new)), so a single
        # plausible-but-wrong date would permanently raise the bar and
        # silently suppress every genuine alert after it. No dates is a
        # visible, recoverable failure; wrong dates is neither.
        if not _select_cinema(page, target.cinema):
            return Snapshot(target_id=target.id, dates=[], movies=[])

        page.wait_for_timeout(SETTLE_MS)
        html = page.content()
        strip = parse_strip_dates(html, date.today())
        if not strip:
            return Snapshot(target_id=target.id, dates=[], movies=[])

        movie = parse_movie_meta(html)
        return Snapshot(
            target_id=target.id,
            # sorted(set(...)) is what detect() requires: zero-padded ISO
            # dates in ascending order.
            dates=sorted(set(strip)),
            movies=[
                Movie(
                    title=movie.title,
                    poster_url=movie.poster_url,
                    rating=movie.rating,
                    runtime_min=movie.runtime_min,
                    language=movie.language,
                    showtimes=_collect_showtimes(page, strip),
                )
            ],
        )
