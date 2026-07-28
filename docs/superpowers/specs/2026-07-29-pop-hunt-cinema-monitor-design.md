# pop-hunt — Cinema Booking-Day Monitor & Dashboard

**Date:** 2026-07-29
**Status:** Approved design, ready for implementation planning

## 1. Purpose

Two goals, served by one scrape:

1. **Alert** the user the moment a tracked cinema opens a **new bookable day**.
   Egyptian cinemas sell tickets on a rolling window (currently ~7 days ahead);
   when the furthest bookable date advances (e.g. 5 Aug → 6 Aug), a new day has
   opened. Alerts go to **Telegram**.
2. **Display** a simple web dashboard showing what is currently bookable —
   movies, posters, and showtimes per cinema — plus a feed of recent new-day
   events, so the user can stay up to speed at a glance.

The user monitors multiple cinema chains and tracks both:

- **Cinema-level** targets — the cinema's booking window across all movies.
- **Movie-level** targets — a specific movie's window at a specific cinema.

## 2. Core concept: the watch target and the snapshot

A **watch target** is any URL that renders bookable dates. Each run renders the
target once and produces a **snapshot**: the set of bookable dates plus the
movies, showtimes, and poster art on that page.

The snapshot has two consumers:

- **Detector** — uses only `snapshot.dates`. If the furthest date is later than
  the furthest previously seen for that target, a new booking day has opened →
  Telegram alert.
- **Dashboard** — uses the whole snapshot to render the site.

One render, two consumers. Adapters are written once and serve both features.

**Definition — a bookable date:** a date counts only if the rendered page shows
**at least one showtime** for it, not merely a date tab. This keeps movie-level
targets correct when a movie has no showtimes on a day the cinema is otherwise
open. Availability is deliberately *not* part of this test — a date whose
showtimes are all sold out or already past still counts, because the day has
opened, which is the event being detected.

## 3. Approach

Headless-browser-for-everything (chosen for resilience): every target renders in
headless Chromium via **Playwright**. This uniformly handles VOX's Akamai bot
protection, Premiere's Next.js client-side rendering, and Scene's server-rendered
pages without per-site network workarounds. Runs on a **GitHub Actions** cron
every 30 minutes in a **private** repo. Data persists as JSON committed to the
repo. The dashboard is a static single-page app built by the same workflow and
deployed to **Cloudflare Pages**, which serves from a private repo on its free
tier and gives a URL reachable from the user's phone.

Stack:

- **Monitor:** Python 3.12, Playwright (Chromium), PyYAML, `requests` (Telegram
  API), pytest.
- **Dashboard:** Vite, React 19, TanStack Router (file-based routing),
  TypeScript, Vitest.

## 4. The three sites (observed 2026-07-29)

All three currently show the same rolling window: Thu 30 Jul → Wed 5 Aug.

| Site | `site` id | Rendering | Notes |
|------|-----------|-----------|-------|
| VOX Cinemas (`egy.voxcinemas.com`) | `vox` | Server HTML, Akamai bot manager | Date strip is **links** carrying `?…&d=YYYYMMDD`, so each day is fetched by URL. Selected day renders as `Today`/`Tomorrow` with no date. Movies are `article.movie-compare`; showtimes grouped by `<strong>` experience (MAX, GOLD, 4DX, Standard), `unavailable` class when not bookable. |
| Premiere (`premiere-cinemas.com`) | `premiere` | Next.js SPA, Cloudflare | Renders "Invalid Date" and a cinema chooser until a location is picked; chooser is `<button>`s identified only by text. Tracked location **Cima Arkan**. Clicking did not render showtimes during investigation; the booking window *is* present in the embedded page payload as ISO dates. |
| Scene (`district5.scenecinemas.com`) | `scene` | Server HTML | Machine-readable dates (`30-07-2026`) in `li.calanderdays`; tabs call `LoadShowtimes('DD-MM-YYYY')`. Experience blocks `div.ex_vip_content` / `div.ex_stand_content`; `showtime_soldout` marks sold out. Subdomain = location. |

The sites share a **date tab strip + showtimes for the selected date** pattern,
but differ in how a date is selected, so each adapter picks its own mechanism:
VOX navigates by URL, Scene clicks the tab, Premiere selects a cinema first.
Preferring a URL or a machine-readable date attribute over clicking is the rule
wherever a site offers one.

## 5. Architecture

Pure logic (parsing, detection, formatting) is separated from side-effecting
adapters (browser, network, disk), so the core is testable without network.

| Unit | Responsibility | Pure? |
|------|----------------|-------|
| `config` | Load `targets.yaml`; read settings/secrets from environment | pure load |
| `models` | `Showtime`, `Movie`, `Snapshot`, `Detection` dataclasses + JSON (de)serialization | pure |
| `fetcher` | Playwright driver: launch browser, open target URL, hand page to adapter | side-effect |
| `adapters/base` | `SiteAdapter` protocol + shared date-tab walking loop | mixed |
| `adapters/{vox,premiere,scene}` | Per-site selectors + date/showtime/movie parsing | pure parts testable |
| `detector` | Previous furthest vs snapshot dates → `Detection` | pure |
| `store` | Load/save `state.json`, `data/snapshot.json`, `data/events.json` with write-if-changed semantics | side-effect |
| `notifiers/format` | Build alert message text | pure |
| `notifiers/telegram` | Send via Telegram Bot API | side-effect |
| `main` | Orchestrate a run: fetch → parse → detect → notify → persist | side-effect |
| `site/` | Vite + React 19 + TanStack Router SPA reading the JSON data files | — |
| `.github/workflows/monitor.yml` | Cron, run, commit changed data, build & deploy dashboard | — |

### 5.1 Repository layout

```
pop-hunt/
├── README.md
├── pyproject.toml
├── targets.yaml                # watch targets (human-edited)
├── state.json                  # detection state: target id -> furthest ISO date
├── data/
│   ├── snapshot.json           # latest full snapshot per target (dashboard feed)
│   └── events.json             # append-only log of new-day events (capped)
├── src/pop_hunt/
│   ├── __init__.py
│   ├── main.py                 # entrypoint: python -m pop_hunt.main
│   ├── config.py
│   ├── models.py
│   ├── fetcher.py
│   ├── adapters/
│   │   ├── __init__.py         # registry: site id -> adapter
│   │   ├── base.py
│   │   ├── vox.py
│   │   ├── premiere.py
│   │   └── scene.py
│   ├── detector.py
│   ├── store.py
│   └── notifiers/
│       ├── __init__.py
│       ├── format.py
│       └── telegram.py
├── site/                       # Vite + React 19 + TanStack Router (TypeScript)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts          # tanstackRouter() plugin BEFORE react()
│   ├── tsconfig.json
│   ├── public/data/            # snapshot.json + events.json copied here at build
│   └── src/
│       ├── main.tsx            # router bootstrap
│       ├── types.ts            # TS mirrors of the Python data model
│       ├── lib/data.ts         # cached fetch of /data/*.json
│       ├── lib/format.ts       # pure date/showtime formatting helpers
│       ├── components/         # MovieCard, ShowtimeList, EventFeed, TargetCard
│       └── routes/
│           ├── __root.tsx      # shell: header, nav, Outlet
│           ├── index.tsx       # overview: events feed + target cards
│           └── targets.$targetId.tsx   # movies + showtimes, ?date= search param
├── tests/
│   ├── fixtures/               # saved real HTML per site
│   ├── test_adapters.py
│   ├── test_detector.py
│   ├── test_store.py
│   └── test_format.py
└── .github/workflows/monitor.yml
```

## 6. Data model

```python
@dataclass(frozen=True)
class Showtime:
    time: str                  # as displayed, e.g. "10:45pm"
    experience: str | None     # "MAX" | "GOLD" | "4DX" | "Standard" | "PREMIERE" | ...
    attributes: tuple[str, ...]  # e.g. ("3D",)
    available: bool            # False when sold out / past (VOX `unavailable`,
                               # Scene `showtime_soldout`); rendered dimmed

@dataclass(frozen=True)
class Movie:
    title: str
    poster_url: str | None
    rating: str | None         # "12+"
    runtime_min: int | None
    language: str | None
    showtimes: dict[str, list[Showtime]]   # ISO date -> showtimes that day

@dataclass(frozen=True)
class Snapshot:
    target_id: str
    dates: list[str]           # sorted ISO dates having >= 1 showtime
    movies: list[Movie]
```

Fields that a given site does not expose are `None`/empty — adapters never
fabricate values, and the dashboard renders around missing data.

## 7. Interfaces

### 7.1 Site adapter

```python
class SiteAdapter(Protocol):
    site_id: str
    def collect(self, page, target) -> Snapshot:
        """Render-time extraction. Selects each date tab, reads the movies and
        showtimes shown for it, and returns the assembled Snapshot."""
```

Pure sub-parts each adapter exposes for unit testing against fixtures:

- `parse_tab_date(text) -> str` — `"Thu 30 Jul"` / `"30-07-2026"` → `"2026-07-30"`.
- `parse_showtimes(html) -> list[Showtime]` — showtimes (with experience/attributes) for the selected date.
- `parse_movies(html) -> list[Movie]` — movie titles, posters, and metadata on the page.

`adapters/base` implements the shared "walk the date tabs, merge per-date
results" loop so only selectors and parsing differ per site.

### 7.2 Detector

```python
def detect(previous_furthest: str | None, dates: list[str]) -> Detection
```

`Detection` fields: `status` (`baseline` | `no_change` | `new_day` | `no_dates`),
`new_day_opened: bool`, `previous: str | None`, `new_max: str | None`,
`added: list[str]`.

Rules (ISO `YYYY-MM-DD` strings compare chronologically as plain strings):

- `dates` empty → `no_dates`, no alert. State untouched; logged as a warning.
- `previous_furthest is None` → `baseline`, no alert, `new_max=max(dates)`. Silent first run.
- `max(dates) > previous_furthest` → `new_day`, alert, `added = [d for d in dates if d > previous_furthest]`.
- otherwise → `no_change`, no alert.

State write rule: stored furthest = `max(previous or "", new_max)` — never moves
backwards, so a temporarily incomplete render cannot cause a duplicate alert
later.

### 7.3 Notifier

Telegram only. Best-effort: a send failure is logged and must not crash the run
or block persistence.

`POST https://api.telegram.org/bot<token>/sendMessage` with `chat_id`, `text`,
`parse_mode=HTML`. Active only if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
are set; otherwise alerts are logged and skipped.

## 8. Configuration

### 8.1 `targets.yaml`

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
  - id: premiere-cima-arkan-spiderman
    label: "Premiere Cima Arkan — Spider-Man: Brand New Day"
    site: premiere
    scope: movie
    cinema: "Cima Arkan"    # premiere: cinema to select before dates render
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
```

`scope` is informational (drives the dashboard/alert label); detection is
identical for both scopes. `cinema` is used by the Premiere adapter to pick a
location on pages that require selection. These four are the seed set.

### 8.2 Settings / secrets (environment variables)

| Variable | Purpose | Required |
|----------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot auth (GitHub Actions secret) | yes, for alerts |
| `TELEGRAM_CHAT_ID` | Telegram destination chat (GitHub Actions secret) | yes, for alerts |
| `CHECK_TZ` | Timezone for date logic and timestamps (default `Africa/Cairo`) | no |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Pages deploy auth (GitHub Actions secret) | yes, for dashboard |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account (GitHub Actions secret) | yes, for dashboard |

### 8.3 Persisted data

`state.json` — detection state only:

```json
{ "vox-moe-spiderman": "2026-08-05", "scene-district5-spiderman": "2026-08-05" }
```

`data/snapshot.json` — dashboard feed:

```json
{
  "generated_at": "2026-07-30T09:03:00+03:00",
  "targets": [
    {
      "id": "vox-moe-spiderman",
      "label": "VOX Mall of Egypt — Spider-Man: Brand New Day",
      "url": "https://…",
      "scope": "movie",
      "site": "vox",
      "dates": ["2026-07-30", "…"],
      "movies": [
        {
          "title": "Spider-Man: Brand New Day",
          "poster_url": "https://…",
          "rating": "12+",
          "runtime_min": 140,
          "language": "English",
          "showtimes": {
            "2026-07-30": [
              {"time": "10:45am", "experience": "MAX", "attributes": []},
              {"time": "12:00pm", "experience": "Standard", "attributes": ["3D"]}
            ]
          }
        }
      ],
      "status": "ok"
    }
  ]
}
```

`data/events.json` — append-only new-day log, capped at the most recent 200:

```json
[
  {
    "at": "2026-07-30T09:03:00+03:00",
    "target_id": "vox-moe-spiderman",
    "label": "VOX Mall of Egypt — Spider-Man: Brand New Day",
    "previous": "2026-08-05",
    "new_max": "2026-08-06",
    "added": ["2026-08-06"],
    "url": "https://…"
  }
]
```

The per-target `status` is a **display** vocabulary, distinct from the
detector's status: `ok` (rendered fine this run), `stale` (render failed or
returned no dates; entry carried over from the previous run, with
`stale_since` set), or `error` (failed and no previous entry exists, so no
movies can be shown).

**Write-if-changed:** `snapshot.json` is rewritten only when its content
excluding `generated_at` differs from what is on disk. Without this, every run
would produce a commit; with it, commits happen only on real change (~once a
day). `events.json` is appended only on a `new_day` detection.

## 9. Run flow (`main`)

```
settings = load_settings(env);  targets = load_targets();  state = load_state()
previous = load_snapshot()           # last run's entries, for carry-over on failure
snapshots, alerts = [], []

with playwright_chromium() as browser:
    for t in targets:
        try:
            snap = fetch_and_collect(browser, t)        # fetcher + site adapter
        except Exception:
            log.warning("target failed", t.id)
            snapshots.append(carry_over(t, previous, now))      # status: stale | error
            continue
        det = detect(state.get(t.id), snap.dates)
        if det.status == "no_dates":
            log.warning("no dates", t.id)
            snapshots.append(carry_over(t, previous, now))      # status: stale | error
            continue
        snapshots.append(entry(t, snap, status="ok"))
        if det.new_day_opened:
            alerts.append((t, det))
        state[t.id] = max(state.get(t.id, ""), det.new_max)

for (t, det) in alerts:
    send_telegram(settings, format_alert(t, det))   # guarded, never raises
    append_event(t, det, now)

save_state(state)                    # write-if-changed
save_snapshot(snapshots)             # write-if-changed (ignoring generated_at)
```

A target that fails to render keeps its **previous** snapshot entry on the
dashboard, marked stale, rather than disappearing from the page.

## 10. Alert format (Telegram)

```
🎬 New booking day

{label}
Now selling through {new_max} (was {previous}).
New date(s): {added}
Book: {url}
```

## 11. Dashboard

A **Vite + React 19** single-page app using **TanStack Router** file-based
routing, written in TypeScript. It is a static build (no server, no SSR) that
fetches `data/snapshot.json` and `data/events.json` at runtime.

**Routes:**

| Route | File | Shows |
|-------|------|-------|
| `/` | `routes/index.tsx` | Recent-openings feed + a card per target |
| `/targets/$targetId` | `routes/targets.$targetId.tsx` | That target's movies, posters, and showtimes |

The target route takes a typed search param `?date=YYYY-MM-DD` selecting the day
whose showtimes are shown, validated with `validateSearch` and defaulting to the
earliest bookable date. This makes a given day linkable and survives reload —
the natural fit for TanStack Router's typed-search-param API, and it mirrors the
cinemas' own date-strip pattern.

**Data loading:** `src/lib/data.ts` exposes `loadDashboard()` — a single fetch of
both JSON files, memoised in a module-level promise. Route `loader`s call it, so
navigating between routes never refetches. Types in `src/types.ts` mirror the
Python data model exactly.

**Sections:**

1. **Header** — "Last checked {built_at}" and "Data as of {generated_at}".
2. **Recent openings** — reverse-chronological feed from `events.json`: which
   target opened which date, and when.
3. **Per-target cards** — label, booking window (`through {furthest}`), a
   stale/error badge when the last render failed, and a link into the target route.
4. **Movies & showtimes** — poster, title, rating, runtime, language; showtimes
   for the selected date labelled with experience (MAX/GOLD/4DX/PREMIERE/
   Standard) and attributes (3D). Sold-out/unavailable times are shown dimmed
   rather than hidden, so a day never looks empty.

**Poster images** are hot-linked from the cinemas' CDNs with
`referrerpolicy="no-referrer"` and `loading="lazy"`; a CSS placeholder covers
images that fail to load. No binaries are committed to the repo.

Responsive (usable on phone), dark cinema-styled, and fully functional as a
read-only view — there are no controls that mutate anything.

## 12. GitHub Actions workflow

`.github/workflows/monitor.yml`:

- `on.schedule: cron '*/30 * * * *'` plus `workflow_dispatch` for manual runs.
- `concurrency: { group: monitor, cancel-in-progress: false }` — no overlapping runs.
- `permissions: { contents: write, deployments: write }`.
- Steps: checkout → setup-python 3.12 → `pip install -e .` →
  `playwright install --with-deps chromium` → `python -m pop_hunt.main`
  (Telegram secrets in env) → commit `state.json` + `data/` **only if changed**
  (`git diff --quiet || commit && push`, message tagged `[skip ci]`) → copy
  `data/*.json` into `site/public/data/` and write `built_at` → setup-node →
  `npm ci && npm run build` in `site/` → deploy `site/dist` with
  `cloudflare/wrangler-action@v3`:

```yaml
- uses: cloudflare/wrangler-action@v3
  with:
    apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    command: pages deploy site/dist --project-name=pop-hunt
```

The dashboard deploys **every run** so "last checked" stays fresh, while the
repo is committed to only on real data change. Cloudflare Pages' free tier
deploys from a private repo via this direct-upload path — the repo is never
connected to Cloudflare, the workflow just uploads the built directory.

GitHub cron is best-effort and can lag several minutes under load; acceptable
since new days open ~once daily.

**Repo visibility:** the repo is **private**. The Telegram and Cloudflare
tokens live in GitHub Actions secrets, never in the repo. Note the deployed
`*.pages.dev` URL is reachable by anyone who knows it; the data is public
cinema listings, so this is acceptable. To restrict it, put **Cloudflare
Access** in front of the project (free tier covers up to 50 users) — a
dashboard-only change that does not affect the monitor.

## 13. Edge cases

- **Date strip without a year** (a strip rendering `Thu 30 Jul`): infer the year
  from today in `CHECK_TZ`, rolling forward when the parsed month precedes the
  current month (Dec→Jan boundary). Not needed by any adapter today — VOX
  exposes `d=YYYYMMDD` and Scene `DD-MM-YYYY` — but kept as the fallback for a
  site that drops its machine-readable dates.
- **Target yields zero dates** (movie ended, redesign, render failure):
  `no_dates` → warning, state untouched, no false alert, previous dashboard
  entry retained and marked stale.
- **First run / newly added target:** `baseline` records the furthest date silently.
- **No duplicate alerts:** alert only when `max(dates) > stored`; stored never regresses.
- **Overlapping runs:** prevented by the `concurrency` group.
- **Telegram unconfigured or failing:** logged; run still succeeds and data still persists.
- **Poster hot-link blocked:** image fails → CSS placeholder; never breaks the page.
- **Timezone:** all date logic and timestamps use `Africa/Cairo`.

## 14. Testing strategy

- **Adapters:** save real rendered HTML from each site as fixtures; unit-test
  `parse_tab_date`, `parse_showtimes`, `parse_movies`, and the shared collector
  against a fixture DOM. No network in tests.
- **Dashboard:** Vitest over the pure helpers in `lib/format.ts` and
  `lib/data.ts` (parsing/grouping/formatting), plus render smoke tests for the
  two routes against a fixture snapshot. No network in tests.
- **Detector:** table-driven over `baseline`, `no_change`, `new_day` (single and
  multiple added dates), `no_dates`, and the never-regress rule.
- **Store:** write-if-changed semantics (unchanged content → no rewrite;
  `generated_at`-only difference → no rewrite), events appending and capping.
- **Formatter:** assert message text for a sample detection.
- **Fetcher / Telegram:** thin side-effect adapters; light smoke tests with the
  browser and network mocked.

Test-driven: write the failing test against fixtures before implementing each
unit.

## 15. Build phases

**Phase 1 — monitor (delivers the core need):** models, config, adapters +
fixtures, detector, store, Telegram notifier, `main`, workflow cron with commit.
Alerting is live and correct at the end of this phase.

**Phase 2 — dashboard:** snapshot/events data files wired through, the Vite +
React 19 + TanStack Router SPA, and Cloudflare Pages deployment.

The adapters capture full snapshot data from Phase 1, so Phase 2 adds no
scraping work — only presentation.

## 16. Setup the user performs (documented in README)

1. **Telegram:** create a bot via **@BotFather** → copy `TELEGRAM_BOT_TOKEN`;
   message the bot, then read `chat_id` from
   `https://api.telegram.org/bot<token>/getUpdates` → set `TELEGRAM_CHAT_ID`.
2. **Cloudflare:** create a free account; create a Pages project named
   `pop-hunt` (Direct Upload, no Git connection); create an API token with the
   **Cloudflare Pages: Edit** permission → `CLOUDFLARE_API_TOKEN`; copy the
   account ID from the dashboard → `CLOUDFLARE_ACCOUNT_ID`.
3. **Repo:** push to a **private** GitHub repo, add all four values as **Actions
   secrets**, and enable Actions.
4. Trigger `workflow_dispatch` once to verify, then the cron takes over.
5. *(Optional)* Put **Cloudflare Access** in front of the Pages project to
   require a login before the dashboard is viewable.

## 17. Out of scope (possible future work)

- Detecting brand-new movie titles (as opposed to new dates).
- Price, seat-availability, or sold-out tracking.
- Per-target schedules or quiet hours.
- Historical charts of booking-window behaviour.
- Additional cinema chains (added by writing a new adapter + fixtures).
