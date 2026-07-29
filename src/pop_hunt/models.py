"""Data model shared by the detector and the dashboard feed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Showtime:
    """A single screening. `available` is False when sold out or already past."""

    time: str
    experience: str | None = None
    attributes: tuple[str, ...] = ()
    available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "experience": self.experience,
            "attributes": list(self.attributes),
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Showtime:
        return cls(
            time=data["time"],
            experience=data.get("experience"),
            attributes=tuple(data.get("attributes") or ()),
            available=bool(data.get("available", True)),
        )


@dataclass(frozen=True)
class Movie:
    title: str
    poster_url: str | None = None
    rating: str | None = None
    runtime_min: int | None = None
    language: str | None = None
    showtimes: dict[str, list[Showtime]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "poster_url": self.poster_url,
            "rating": self.rating,
            "runtime_min": self.runtime_min,
            "language": self.language,
            "showtimes": {
                date: [st.to_dict() for st in times]
                for date, times in self.showtimes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Movie:
        return cls(
            title=data["title"],
            poster_url=data.get("poster_url"),
            rating=data.get("rating"),
            runtime_min=data.get("runtime_min"),
            language=data.get("language"),
            showtimes={
                date: [Showtime.from_dict(st) for st in times]
                for date, times in (data.get("showtimes") or {}).items()
            },
        )


@dataclass(frozen=True)
class Snapshot:
    """One render of one target: the dates that are bookable, and what's on."""

    target_id: str
    dates: list[str]
    movies: list[Movie]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "dates": list(self.dates),
            "movies": [m.to_dict() for m in self.movies],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(
            target_id=data["target_id"],
            dates=list(data.get("dates") or []),
            movies=[Movie.from_dict(m) for m in (data.get("movies") or [])],
        )
