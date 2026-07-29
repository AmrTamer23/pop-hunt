from pop_hunt.config import Target
from pop_hunt.detector import detect
from pop_hunt.notifiers.format import format_alert

TARGET = Target(
    id="scene-district5-spiderman",
    label="Scene District 5 — Spider-Man",
    site="scene",
    url="https://district5.scenecinemas.com/movie-details/spider-man.html",
)


def test_alert_contains_label_dates_and_url():
    detection = detect("2026-08-05", ["2026-08-05", "2026-08-06"])
    text = format_alert(TARGET, detection)

    assert "New booking day" in text
    assert "Scene District 5 — Spider-Man" in text
    assert "2026-08-06" in text
    assert "was 2026-08-05" in text
    assert TARGET.url in text


def test_alert_lists_every_added_date():
    detection = detect("2026-08-05", ["2026-08-06", "2026-08-07"])
    assert "2026-08-06, 2026-08-07" in format_alert(TARGET, detection)


def test_alert_escapes_html_in_the_label():
    target = Target(id="x", label="Cinema <B> & Co", site="scene", url="https://x.test")
    detection = detect("2026-08-05", ["2026-08-06"])
    text = format_alert(target, detection)

    assert "&lt;B&gt;" in text
    assert "&amp;" in text
    assert "<B>" not in text


def test_alert_escapes_html_in_the_url():
    target = Target(id="x", label="Cinema", site="scene", url="https://x.test/?a=1&b=2")
    detection = detect("2026-08-05", ["2026-08-06"])
    text = format_alert(target, detection)

    assert "&amp;" in text
    assert "?a=1&b=2" not in text
