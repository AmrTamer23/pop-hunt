"""Playwright lifecycle. The only module that knows a browser exists."""

from __future__ import annotations

import logging
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from pop_hunt.config import Target
from pop_hunt.models import Snapshot

log = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 60_000
SETTLE_MS = 3_000
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


@contextmanager
def browser_session():
    """A headless real-Chrome browser.

    channel="chrome" uses real Chrome, not Playwright's bundled Chromium. VOX
    sits behind Akamai bot management, which rejects the bundled build at the
    HTTP/2 layer (net::ERR_HTTP2_PROTOCOL_ERROR) before any content loads. Real
    Chrome is accepted. Scene and Premiere work with either, so this is the
    single launch config for all three.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="chrome")
        try:
            yield browser
        finally:
            browser.close()


def collect_target(browser, target: Target, adapter) -> Snapshot:
    """Render one target in its OWN context and hand the page to its adapter.

    A fresh context per target is deliberate, not tidiness: VOX rejects the
    second request made from a reused context with
    net::ERR_HTTP2_PROTOCOL_ERROR, even though the same URL loads fine on its
    own. Isolating each target makes the run reproducible.
    """
    context = browser.new_context(user_agent=USER_AGENT, locale="en-GB")
    page = context.new_page()
    try:
        log.info("rendering %s", target.id)
        # domcontentloaded, NOT networkidle: VOX holds background connections
        # open indefinitely, so networkidle never fires and goto times out even
        # though the page rendered in ~2s. SETTLE_MS covers the rest.
        page.goto(target.url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        page.wait_for_timeout(SETTLE_MS)
        return adapter.collect(page, target)
    finally:
        page.close()
        context.close()
