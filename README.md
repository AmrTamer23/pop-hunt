# pop-hunt

Egyptian cinemas sell tickets on a rolling ~7-day window — at any moment you
can book up to some furthest date, and no further. When that furthest
bookable date advances, a new day has just opened for booking. pop-hunt
watches a list of cinema and movie pages for exactly that event and sends a
Telegram alert when it happens.

## How it works

Every 30 minutes, a GitHub Actions job renders each URL in `targets.yaml`
with headless real Chrome, extracts the dates that currently have showtimes,
and compares the furthest one to the last-seen value for that target in
`state.json`. If it advanced, you get a Telegram message.

Each run also writes `data/snapshot.json` (what's showing right now, per
target) and appends to `data/events.json` (a log of the openings that have
been detected). Neither is consumed yet — a Phase 2 dashboard will read them.

## Setup

### Telegram

1. Message [`@BotFather`](https://t.me/BotFather) and send `/newbot`. Follow
   the prompts and copy the token it gives you.
2. Send your new bot any message — a bot cannot message you first, so it
   needs one message from you before it can reply.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
   (with your token in place of `<YOUR_TOKEN>`) and copy
   `result[0].message.chat.id`.

### GitHub

1. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as repository secrets:
   Settings -> Secrets and variables -> Actions.
2. Run the workflow once by hand: Actions -> monitor -> Run workflow.

**The first run for every target records a baseline and sends no alert.**
That's expected, not a bug — there is nothing yet to compare that first
observation against. You'll start getting alerts once a target's furthest
bookable date advances past what that first run recorded.

## Adding or changing a target

Targets live in `targets.yaml`. Here's a real entry from that file:

```yaml
targets:
  - id: premiere-cima-arkan-spiderman
    label: "Premiere Cima Arkan — Spider-Man: Brand New Day"
    site: premiere
    scope: movie
    cinema: "Cima Arkan"
    url: "https://www.premiere-cinemas.com/en/movie-details/9961.764/1"
```

- **`id`** — unique across the file; loading raises an error at startup if
  two targets share one.
- **`label`** — the human-readable name shown in the Telegram alert.
- **`site`** — which adapter renders the page: `vox`, `scene`, or `premiere`.
- **`scope`** — `movie` or `cinema`. Informational only: it describes what
  the URL represents for the dashboard and doesn't change how the target is
  rendered or detected.
- **`url`** — the page to render.
- **`cinema`** — Premiere only. The location to select in Premiere's "CHOOSE
  YOUR CINEMA" step, matched against the button's exact text (e.g.
  `Cima Arkan`).

A newly added target baselines on its first run just like above — no alert
until there's a prior value to compare against.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install --with-deps chrome
.venv/bin/pytest                       # 121 tests, none touch the network
.venv/bin/python -m pop_hunt.main      # a real run, ~2.5 minutes
```

## When a cinema redesigns its site

Adapter tests run against saved HTML in `tests/fixtures/`, not the live site.
When one starts failing:

1. Refresh the fixtures: `.venv/bin/python scripts/capture_fixtures.py <target_id>`.
2. Update the selectors in `src/pop_hunt/adapters/<site>.py` until the tests
   pass again.

Each adapter also has a "real fixture" guard test whose only job is to fail
loudly the moment a site changes, even if nothing else catches it.

## Notes and limitations

- **Real Chrome is required** (`channel="chrome"`), not Playwright's bundled
  Chromium — VOX's bot management rejects the bundled build at the HTTP/2
  layer before any content loads.
- **VOX records showtimes only for the day the page opens on.** Its other
  bookable dates are still detected — they come from the date strip — just
  not drilled for showtimes, because VOX rejects a second request made from
  the same browser context. Detection of new days is unaffected.
- **For a `scope: cinema` target, every movie currently carries the same
  showtimes list** — showtimes aren't split out per movie yet.
- **The repo is public on purpose.** GitHub Actions minutes are free on
  public repos and limited on private ones, and this monitor's 30-minute
  cadence would run well past a private repo's free allowance. No secrets
  are stored in the repo — the Telegram token and chat ID live only as
  GitHub Actions secrets.
