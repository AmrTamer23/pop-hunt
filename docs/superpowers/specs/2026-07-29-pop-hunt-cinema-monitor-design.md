# pop-hunt — Cinema Booking-Day Monitor

**Date:** 2026-07-29
**Status:** Approved design, ready for implementation planning

## 1. Purpose

Alert the user the moment a tracked cinema opens a **new bookable day** for
tickets. Egyptian cinemas sell tickets on a rolling window (currently ~7 days
ahead). When the furthest bookable date advances (e.g. from 5 Aug to 6 Aug), a
new day has opened — that is the event to detect and alert on.

The user monitors multiple cinema chains and wants alerts on both:

- **Cinema-level** targets — the cinema's furthest bookable date across all movies.
- **Movie-level** targets — a specific movie's furthest bookable date at a cinema.

## 2. Core concept: the watch target

A **watch target** is any URL that renders a set of bookable dates. The engine
renders the page, extracts the set of dates that actually have showtimes, and
remembers the **furthest** one per target. When a later date appears than was
previously seen for that target, a new booking day has opened → alert.

This single abstraction covers both scopes:

- A cinema-level URL renders all movies, so its date set is the cinema's whole
  booking window.
- A movie-level URL renders one movie, so its date set is that movie's window.

The detection logic is identical for both; only the URL differs.

**Definition — a bookable date:** a date counts for a target only if the
rendered page shows **at least one showtime** for it, not merely a date tab.
This keeps movie-level targets correct when a movie has no showtimes on a day
the cinema is otherwise open.

## 3. Approach

Headless-browser-for-everything (chosen for resilience): every target is
rendered in headless Chromium via **Playwright**. This uniformly handles VOX's
Akamai bot protection, Premiere's Next.js client-side rendering, and Scene's
server-rendered pages without per-site network hacks. Runs on a **GitHub
Actions** cron every 30 minutes. State persists as a JSON file committed back to
the repo between runs. Alerts go to **Telegram** and **email**.

Stack: Python 3.12, Playwright (Chromium), PyYAML (target config), `requests`
(Telegram API), stdlib `smtplib`/`email` (email), pytest (tests).

## 4. The three sites (observed 2026-07-29)

All three currently show the same rolling window: Thu 30 Jul → Wed 5 Aug.

| Site | `site` id | Rendering | Date signal in DOM | Notes |
|------|-----------|-----------|--------------------|-------|
| VOX Cinemas (`egy.voxcinemas.com`) | `vox` | Server HTML, Akamai bot manager | Date strip (`Thu 30 Jul` …), showtimes per selected date | Cinema URL: `…/showtimes?c=<cinema>`; movie URL adds `&m=<movie>` |
| Premiere (`premiere-cinemas.com`) | `premiere` | Next.js SPA + JSON API (`mifcentral-api…`), Cloudflare | Rendered after choosing a cinema | Movie URL: `…/movie-details/<id>/1` |
| Scene (`district5.scenecinemas.com`) | `scene` | Server HTML | Machine-readable dates (`30-07-2026`) + showtimes | Subdomain = cinema location |

Common UI pattern across all three: a **date tab strip** at the top, with
showtimes for the **selected** date shown below; switching dates is client-side.
Therefore, to know which dates actually have showtimes, the site adapter selects
each date tab (or reads all pre-rendered date panels if present) and checks for
showtimes.

## 5. Architecture

Each unit has one responsibility, a clear interface, and is testable in
isolation. Pure logic (parsing, detection, formatting) is separated from
side-effecting adapters (browser, network, disk).

| Unit | Responsibility | Pure? |
|------|----------------|-------|
| `config` | Load `targets.yaml`; read settings/secrets from environment | pure load |
| `fetcher` | Playwright driver: launch browser, open page, hand to adapter, return dates | side-effect |
| `adapters/base` | `SiteAdapter` contract + generic date-collection loop | mixed |
| `adapters/{vox,premiere,scene}` | Per-site selectors: find date tabs → ISO date, select a date, detect showtimes | pure parts testable |
| `detector` | Compare previous furthest vs current dates → detection result | pure |
| `state` | Load/save `state.json` (target id → furthest ISO date) | side-effect |
| `notifiers/format` | Build alert subject + body text | pure |
| `notifiers/telegram` | Send message via Telegram Bot API (if configured) | side-effect |
| `notifiers/email` | Send message via SMTP (if configured) | side-effect |
| `main` | Orchestrate one run: fetch → parse → detect → notify → save state | side-effect |
| `.github/workflows/monitor.yml` | Cron schedule, environment, commit updated state | — |

### 5.1 Repository layout

```
pop-hunt/
├── README.md
├── pyproject.toml              # deps + package metadata
├── targets.yaml                # watch targets (human-edited)
├── state.json                  # last-seen furthest date per target (bot-updated)
├── src/pop_hunt/
│   ├── __init__.py
│   ├── main.py                 # orchestrator / entrypoint (python -m pop_hunt.main)
│   ├── config.py               # load targets + settings
│   ├── fetcher.py              # Playwright runner
│   ├── adapters/
│   │   ├── __init__.py         # registry: site id -> adapter
│   │   ├── base.py             # SiteAdapter protocol + collect_dates loop
│   │   ├── vox.py
│   │   ├── premiere.py
│   │   └── scene.py
│   ├── detector.py
│   ├── state.py
│   └── notifiers/
│       ├── __init__.py
│       ├── format.py
│       ├── telegram.py
│       └── email.py
├── tests/
│   ├── fixtures/               # saved real HTML per site + rendered states
│   ├── test_adapters.py
│   ├── test_detector.py
│   └── test_format.py
└── .github/workflows/monitor.yml
```

## 6. Interfaces

### 6.1 Site adapter

```python
class SiteAdapter(Protocol):
    site_id: str
    def collect_dates(self, page) -> list[str]:
        """Return sorted, unique ISO dates (YYYY-MM-DD) that have >=1 showtime
        for this target on the rendered page. May select date tabs as needed."""
```

The pure sub-parts each adapter exposes for unit testing against fixtures:

- `parse_tab_date(text) -> str` — e.g. `"Thu 30 Jul"` or `"30-07-2026"` → `"2026-07-30"`.
- `has_showtimes(html) -> bool` — DOM for a selected date shows ≥1 showtime.

A generic collector in `adapters/base` walks the tabs using the adapter's
selectors, so only selectors/date-parsing differ per site.

### 6.2 Detector

```python
def detect(previous_furthest: str | None, current_dates: list[str]) -> Detection
```

`Detection` fields: `status` (`baseline` | `no_change` | `new_day` | `no_dates`),
`new_day_opened: bool`, `previous: str | None`, `new_max: str | None`,
`added: list[str]`.

Rules (ISO `YYYY-MM-DD` strings compare chronologically as plain string compare):

- `current_dates` empty → `no_dates`, `new_day_opened=False`. State unchanged; logged as a warning.
- `previous_furthest is None` → `baseline`, `new_day_opened=False`, `new_max=max(current)`. Establishes baseline silently (no alert).
- `max(current) > previous_furthest` → `new_day`, `new_day_opened=True`, `added = [d for d in current if d > previous_furthest]`.
- otherwise → `no_change`, `new_day_opened=False`.

State write rule: stored furthest = `max(previous or "", new_max)`; write file
only if any value changed (keeps commit noise to ~once/day).

### 6.3 Notifiers

Both are best-effort and independent — a failure or missing config in one must
not block the other, and neither must crash the run.

- **Telegram:** `POST https://api.telegram.org/bot<token>/sendMessage` with
  `chat_id`, `text`, `parse_mode=HTML`, `disable_web_page_preview=false`. Active
  only if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set.
- **Email:** SMTP over SSL (or STARTTLS) via `smtplib`. Active only if
  `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`, `EMAIL_TO`
  are set.

## 7. Configuration

### 7.1 `targets.yaml`

```yaml
targets:
  - id: vox-moe-spiderman
    label: "VOX Mall of Egypt — Spider-Man: Brand New Day"
    site: vox
    scope: movie            # movie | cinema
    url: "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man-brand-new-day"
  - id: vox-moe-all
    label: "VOX Mall of Egypt — all movies"
    site: vox
    scope: cinema
    url: "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt"
  - id: scene-district5-spiderman
    label: "Scene District 5 — Spider-Man: Brand New Day"
    site: scene
    scope: movie
    url: "https://district5.scenecinemas.com/movie-details/spider-man-brand-new-day.html"
  - id: premiere-spiderman
    label: "Premiere — Spider-Man: Brand New Day"
    site: premiere
    scope: movie
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
```

`scope` is informational (drives the alert label "all movies" vs the movie
name); detection is identical for both. The four targets above are the initial
seed set; the user adds/edits freely.

### 7.2 Settings / secrets (environment variables)

| Variable | Purpose | Required |
|----------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot auth | for Telegram |
| `TELEGRAM_CHAT_ID` | Telegram destination chat | for Telegram |
| `SMTP_HOST` / `SMTP_PORT` | Mail server | for email |
| `SMTP_USER` / `SMTP_PASS` | Mail auth (app password) | for email |
| `EMAIL_FROM` / `EMAIL_TO` | Sender / recipient | for email |
| `CHECK_TZ` | Timezone for "today"/timestamps (default `Africa/Cairo`) | no |

### 7.3 `state.json`

```json
{
  "vox-moe-spiderman": "2026-08-05",
  "scene-district5-spiderman": "2026-08-05"
}
```

## 8. Run flow (`main`)

```
settings = load_settings(environment)
targets  = load_targets("targets.yaml")
state    = load_state("state.json")
alerts   = []

with playwright_chromium() as browser:
    for t in targets:
        try:
            dates = fetch_and_parse(browser, t)      # fetcher + site adapter
        except Exception:
            log.warning("target failed", t.id); continue
        det = detect(state.get(t.id), dates)
        if det.status == "no_dates":
            log.warning("no dates", t.id); continue
        if det.new_day_opened:
            alerts.append((t, det))
        state[t.id] = max(state.get(t.id, ""), det.new_max)

for (t, det) in alerts:
    msg = format_alert(t, det, tz=settings.tz)
    send_telegram(settings, msg)     # best-effort, guarded
    send_email(settings, msg)        # best-effort, guarded

save_state("state.json", state)      # workflow commits if changed
```

## 9. Alert format

Subject: `🎬 New booking day — {label}`

Body:

```
{label}
Now selling through {new_max} (was {previous}).
New date(s): {added, comma-separated}
Book: {url}
Checked: {timestamp in Africa/Cairo}
```

## 10. GitHub Actions workflow

`.github/workflows/monitor.yml`, key elements:

- `on.schedule: cron '*/30 * * * *'` plus `workflow_dispatch` for manual runs.
- `concurrency: { group: monitor, cancel-in-progress: false }` — no overlapping runs.
- `permissions: { contents: write }` — to commit `state.json`.
- Steps: checkout → setup-python 3.12 → `pip install -e .` →
  `python -m playwright install --with-deps chromium` → `python -m pop_hunt.main`
  (with secrets mapped to env) → commit `state.json` only if changed
  (`git diff --quiet state.json || (commit + push)`), commit message tagged
  `[skip ci]`.

Note: GitHub cron is best-effort and can lag several minutes under load; that is
acceptable since new days open ~once daily.

## 11. Edge cases

- **Date strip without a year** (e.g. VOX `Thu 30 Jul`): infer the year from
  today in `CHECK_TZ`, rolling to next year when the parsed month is earlier
  than the current month (Dec→Jan boundary).
- **Target yields zero dates** (movie ended, page redesigned, render failure):
  `no_dates` → logged warning, state untouched, no false alert.
- **First run / new target:** `baseline` establishes the furthest date silently.
- **No duplicate alerts:** alert only when `max(current) > stored`; stored is
  then advanced.
- **Overlapping runs:** prevented by the `concurrency` group.
- **One notifier failing/unconfigured:** other still fires; run still succeeds.
- **Timezone:** all "today" logic and timestamps use `Africa/Cairo`.

## 12. Testing strategy

- **Adapters:** save real rendered HTML from each site as fixtures; unit-test
  `parse_tab_date` and `has_showtimes`, and the generic collector against a
  fixture DOM. No network in tests.
- **Detector:** table-driven tests for `baseline`, `no_change`, `new_day`
  (including multiple added dates), and `no_dates`; plus string-date ordering.
- **Formatter:** assert subject/body for a sample detection.
- **Notifiers/fetcher:** thin side-effect adapters; covered by a light smoke
  test with the network/browser mocked, not core unit tests.

Test-driven: write the failing adapter/detector/formatter tests against
fixtures before implementing each unit.

## 13. Setup the user performs (documented in README)

1. **Telegram:** create a bot via **@BotFather** → copy `TELEGRAM_BOT_TOKEN`;
   send the bot a message, then read `chat_id` from
   `https://api.telegram.org/bot<token>/getUpdates` → set `TELEGRAM_CHAT_ID`.
2. **Email (optional):** obtain an SMTP app password from the mail provider; set
   the six `SMTP_*`/`EMAIL_*` variables.
3. **Repo:** push to GitHub, add the above as **Actions secrets**, enable
   Actions. The cron starts automatically; `workflow_dispatch` triggers a manual
   test run.

## 14. Out of scope (possible future work)

- Detecting brand-new movie titles (as opposed to new dates).
- Price, sold-out, or specific-showtime tracking.
- Per-target schedules or quiet hours.
- A web dashboard / historical view.
- Additional cinema chains (added by writing a new adapter + fixtures).
