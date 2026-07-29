import pytest

from pop_hunt.adapters import get_adapter


def test_registry_returns_an_adapter_per_known_site():
    for site in ("scene", "vox", "premiere"):
        assert get_adapter(site).site_id == site


def test_registry_rejects_unknown_sites():
    with pytest.raises(KeyError, match="unknown site"):
        get_adapter("odeon")


def test_registry_covers_every_site_in_targets_yaml():
    """A target whose site has no adapter would fail only at runtime."""
    from pop_hunt.config import load_targets

    for target in load_targets("targets.yaml"):
        assert get_adapter(target.site).site_id == target.site
