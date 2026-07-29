import pytest

from pop_hunt.config import load_settings, load_targets

SAMPLE = """
targets:
  - id: scene-district5-spiderman
    label: "Scene District 5 — Spider-Man"
    site: scene
    scope: movie
    url: "https://district5.scenecinemas.com/movie-details/spider-man-brand-new-day.html"
  - id: premiere-cima-arkan-spiderman
    label: "Premiere Cima Arkan — Spider-Man"
    site: premiere
    scope: movie
    cinema: "Cima Arkan"
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
"""


def test_load_targets_reads_all_fields(tmp_path):
    path = tmp_path / "targets.yaml"
    path.write_text(SAMPLE)

    targets = load_targets(path)

    assert [t.id for t in targets] == [
        "scene-district5-spiderman",
        "premiere-cima-arkan-spiderman",
    ]
    assert targets[0].site == "scene"
    assert targets[0].cinema is None
    assert targets[1].cinema == "Cima Arkan"


def test_load_targets_defaults_scope_to_movie_when_absent(tmp_path):
    path = tmp_path / "targets.yaml"
    path.write_text(
        'targets:\n'
        '  - {id: a, label: A, site: scene, url: "https://x.test"}\n'
    )
    targets = load_targets(path)
    assert targets[0].scope == "movie"


def test_load_targets_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "targets.yaml"
    path.write_text(
        'targets:\n'
        '  - {id: a, label: A, site: scene, url: "https://x.test"}\n'
        '  - {id: a, label: B, site: scene, url: "https://y.test"}\n'
    )
    with pytest.raises(ValueError, match="duplicate target id: a"):
        load_targets(path)


def test_settings_disabled_when_telegram_secrets_absent():
    settings = load_settings({})
    assert settings.telegram_enabled is False
    assert settings.tz == "Africa/Cairo"


def test_settings_enabled_when_both_telegram_secrets_present():
    settings = load_settings(
        {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1", "CHECK_TZ": "UTC"}
    )
    assert settings.telegram_enabled is True
    assert settings.tz == "UTC"


def test_settings_disabled_when_only_one_telegram_secret_present():
    assert load_settings({"TELEGRAM_BOT_TOKEN": "t"}).telegram_enabled is False
