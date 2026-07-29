"""Dev tool: save each target's rendered HTML into tests/fixtures/.

Usage:  python scripts/capture_fixtures.py [target_id ...]

Re-run this when a cinema redesigns its site and an adapter starts failing.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pop_hunt.config import load_targets

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    targets = [t for t in load_targets("targets.yaml") if not wanted or t.id in wanted]
    if not targets:
        print("no matching targets")
        return 1

    FIXTURES.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        for target in targets:
            page = context.new_page()
            print(f"-> {target.id}: {target.url}")
            page.goto(target.url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(3_000)
            out = FIXTURES / f"{target.id}.html"
            out.write_text(page.content(), encoding="utf-8")
            print(f"   saved {out.relative_to(Path.cwd())} ({out.stat().st_size} bytes)")
            page.close()
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
