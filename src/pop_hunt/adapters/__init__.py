"""Registry mapping a target's `site` value to its adapter."""

from __future__ import annotations

from pop_hunt.adapters.base import SiteAdapter
from pop_hunt.adapters.premiere import PremiereAdapter
from pop_hunt.adapters.scene import SceneAdapter
from pop_hunt.adapters.vox import VoxAdapter

_ADAPTERS: dict[str, SiteAdapter] = {
    "scene": SceneAdapter(),
    "vox": VoxAdapter(),
    "premiere": PremiereAdapter(),
}


def get_adapter(site: str) -> SiteAdapter:
    try:
        return _ADAPTERS[site]
    except KeyError:
        raise KeyError(f"unknown site: {site!r}") from None


__all__ = ["SiteAdapter", "get_adapter"]
