import pytest

from pop_hunt.config import Target
from pop_hunt.fetcher import collect_target
from pop_hunt.models import Snapshot

TARGET = Target(id="t1", label="T", site="scene", url="https://x.test")


class _FakePage:
    def __init__(self):
        self.goto_calls = []
        self.closed = False

    def goto(self, url, wait_until, timeout):
        self.goto_calls.append((url, wait_until))

    def wait_for_timeout(self, ms):
        pass

    def close(self):
        self.closed = True


class _FakeContext:
    def __init__(self, page):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, context):
        self._context = context
        self.contexts_created = 0

    def new_context(self, **kwargs):
        self.contexts_created += 1
        return self._context


class _FakeAdapter:
    site_id = "scene"

    def __init__(self):
        self.seen_page = None

    def collect(self, page, target):
        self.seen_page = page
        return Snapshot(target_id=target.id, dates=["2026-08-05"], movies=[])


def test_collect_target_navigates_and_delegates_to_the_adapter():
    page = _FakePage()
    adapter = _FakeAdapter()

    snapshot = collect_target(_FakeBrowser(_FakeContext(page)), TARGET, adapter)

    assert page.goto_calls == [("https://x.test", "domcontentloaded")]
    assert adapter.seen_page is page
    assert snapshot.dates == ["2026-08-05"]


def test_collect_target_does_not_wait_for_networkidle():
    """VOX holds connections open, so networkidle never fires and goto times out."""
    page = _FakePage()
    collect_target(_FakeBrowser(_FakeContext(page)), TARGET, _FakeAdapter())
    assert all(wait != "networkidle" for _url, wait in page.goto_calls)


def test_collect_target_creates_its_own_context():
    """VOX rejects the second request made from a reused context."""
    browser = _FakeBrowser(_FakeContext(_FakePage()))
    collect_target(browser, TARGET, _FakeAdapter())
    assert browser.contexts_created == 1


def test_collect_target_always_closes_page_and_context():
    page = _FakePage()
    context = _FakeContext(page)
    collect_target(_FakeBrowser(context), TARGET, _FakeAdapter())
    assert page.closed is True
    assert context.closed is True


def test_collect_target_closes_everything_even_when_the_adapter_raises():
    page = _FakePage()
    context = _FakeContext(page)

    class Boom:
        site_id = "scene"

        def collect(self, page, target):
            raise RuntimeError("selector gone")

    with pytest.raises(RuntimeError):
        collect_target(_FakeBrowser(context), TARGET, Boom())

    assert page.closed is True
    assert context.closed is True
