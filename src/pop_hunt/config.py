"""Load watch targets from YAML and settings from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

DEFAULT_TZ = "Africa/Cairo"


@dataclass(frozen=True)
class Target:
    id: str
    label: str
    site: str
    url: str
    scope: str = "movie"
    cinema: str | None = None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    tz: str

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def load_targets(path: str | Path) -> list[Target]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    targets: list[Target] = []
    seen: set[str] = set()
    for entry in raw.get("targets") or []:
        target = Target(
            id=entry["id"],
            label=entry["label"],
            site=entry["site"],
            url=entry["url"],
            scope=entry.get("scope", "movie"),
            cinema=entry.get("cinema"),
        )
        if target.id in seen:
            raise ValueError(f"duplicate target id: {target.id}")
        seen.add(target.id)
        targets.append(target)
    return targets


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=env.get("TELEGRAM_CHAT_ID") or None,
        tz=env.get("CHECK_TZ") or DEFAULT_TZ,
    )
