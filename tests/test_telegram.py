from pop_hunt.config import Settings
from pop_hunt.notifiers import telegram

ENABLED = Settings(telegram_bot_token="tok", telegram_chat_id="42", tz="Africa/Cairo")
DISABLED = Settings(telegram_bot_token=None, telegram_chat_id=None, tz="Africa/Cairo")


class _FakeResponse:
    def __init__(self, error: Exception | None = None):
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error


def test_send_posts_to_the_bot_api(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(telegram.requests, "post", fake_post)

    assert telegram.send(ENABLED, "hello") is True
    assert captured["url"] == "https://api.telegram.org/bottok/sendMessage"
    assert captured["json"]["chat_id"] == "42"
    assert captured["json"]["text"] == "hello"
    assert captured["json"]["parse_mode"] == "HTML"


def test_send_skips_when_not_configured(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("must not call the API when unconfigured")

    monkeypatch.setattr(telegram.requests, "post", fail)
    assert telegram.send(DISABLED, "hello") is False


def test_send_returns_false_instead_of_raising_on_api_error(monkeypatch):
    monkeypatch.setattr(
        telegram.requests,
        "post",
        lambda url, json, timeout: _FakeResponse(RuntimeError("429")),
    )
    assert telegram.send(ENABLED, "hello") is False


def test_send_returns_false_instead_of_raising_on_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("connection reset")

    monkeypatch.setattr(telegram.requests, "post", boom)
    assert telegram.send(ENABLED, "hello") is False
