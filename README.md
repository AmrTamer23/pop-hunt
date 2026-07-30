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
been detected). Both are what the [dashboard](#dashboard) renders.

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

### Running it locally on a schedule

The workflow's cron says every 30 minutes, and GitHub does not honour it.
Scheduled workflows are best-effort and heavily throttled: measured gaps
between real runs here have been **71 to 189 minutes**, about eleven runs a
day. For a window that opens once a day at no announced hour, that is a long
time to be looking the other way.

A launchd agent on your Mac fixes the cadence: `StartInterval` of 1800 seconds
is a real 30 minutes, for as long as the machine is awake. While it sleeps the
timer does not fire, and launchd collapses everything it missed into a single
run on wake — a night asleep costs you one catch-up run in the morning, not a
burst of twenty.

**Actions stays on.** It is the fallback for every hour your laptop is shut,
and between them you get a tight cadence when you are around and coverage when
you are not.

**Both schedulers share one state, so neither re-alerts the other's finds.**
`state.json` is committed to this repo, and that is what makes it work:
`scripts/run_local.sh` pulls before the run and pushes after, so whichever
scheduler goes next starts from what the other already saw. Without that they
would each keep private state and both alert for the same day.

#### Install

```bash
cp .env.example .env            # then fill in your bot token and chat id
sed "s|__REPO__|$PWD|g" scripts/com.pophunt.monitor.plist \
    > ~/Library/LaunchAgents/com.pophunt.monitor.plist
launchctl load ~/Library/LaunchAgents/com.pophunt.monitor.plist
```

Run that `sed` from the repo root — `$PWD` is what replaces the `__REPO__`
placeholder in the plist, and launchd needs the absolute path. `RunAtLoad` is
set, so loading it runs the monitor once straight away and you find out
immediately if something is wrong.

#### Check on it

```bash
launchctl list | grep pophunt        # pid, last exit code, label
tail -f /tmp/pop-hunt.local.log      # timestamped log of every run
```

In `launchctl list` the middle column is the last exit status: `0` is a healthy
run. The log shows each run pulling, running, and then either pushing or
reporting `no data change` — an uneventful run writes nothing, so most say the
latter.

#### Stop it

```bash
launchctl unload ~/Library/LaunchAgents/com.pophunt.monitor.plist
```

Actions keeps running after that; unloading only gives up the tighter cadence.

#### If it does not run

- **Nothing in the log, no pid.** The plist still has `__REPO__` in it, or the
  path in it is wrong. Fix it, `launchctl unload`, then `load` again — editing
  a loaded plist changes nothing by itself.
- **`push rejected` twice in the log.** Under launchd the push uses your SSH
  key without a terminal to prompt on, so a passphrase that is not in the
  keychain fails silently. `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`
  once, and it can read it thereafter.
- **Runs skipped with "another run holds …".** Expected if you started a run by
  hand while the timer fired; the lock is there to stop two Chromes fighting
  over the same files. A crashed run leaves the lock behind and the next one
  clears it.

## Dashboard

A read-only site built from the two data files above. The overview page lists
every tracked cinema with the day it currently books through and a badge when
that reading is stale, plus a feed of the booking days that have recently
opened — which target, and which dates appeared.

Open a cinema and you get its bookable days as a strip you can pick from, and
for the chosen day each movie with its poster, rating, language and runtime,
and its showtimes grouped by experience — MAX, GOLD, 4DX, Premiere, Standard.
Sold-out and already-started times stay on the page, dimmed: hiding them makes
a busy evening look empty.

The header carries two timestamps on purpose. "Last checked" is when the
monitor last ran; "data as of" is when anything last changed. On a quiet day
they are hours apart, and showing only the second one looks like a broken site.

### Where it lives

Nowhere — it runs locally, on demand. The dashboard is a static page over the
data files CI commits, so there is nothing to host: pull the repo and start it
when you want to look. CI does not build or deploy it, which keeps the workflow
to five steps and its run under two minutes.

To publish it later, add a build step and a deploy step for whichever host you
pick; `npm run build` already produces a self-contained `site/dist`.

### Running the dashboard

```bash
mkdir -p site/public/data
cp data/*.json site/public/data/
cd site && npm install && npm run dev
```

**The copy is required.** `site/public/data/` is gitignored — it is a build
input, not source — and the page fetches `/data/snapshot.json` at runtime.
Skip it and the site loads with no cinemas on it and no error: a missing data
file is a legitimate state here (see the last note below), so the page falls
back to empty rather than failing.

Run `git pull` first if you want the latest data — CI commits it, and your
local copy is only as fresh as your last pull.

Dashboard tests are `cd site && npx vitest run`; `npm run build` type-checks
and produces a deployable `site/dist`.

### What it will and won't tell you

- **VOX showtimes are collected for one day only.** VOX rejects a second
  showtimes request made from the same browser context, so only the day its
  page opens on gets drilled. Every other bookable day says "Showtimes not
  collected for this day" — the dashboard will not render an empty list there,
  because that would claim the cinema is shut when what we actually have is no
  information. The booking window itself comes from the date strip and is
  complete.
- **Premiere is currently failing to render on their side.** Their page paints
  the similar-movies strip and the footer but never the movie hero or the
  cinema chooser, so there is nothing for the adapter to click. Expect that
  card to carry a stale badge and show the last reading that worked. The
  monitor reports no dates rather than guessing at them, so a Premiere outage
  produces silence, never a false alert.
- **Posters are hot-linked from the cinemas' own CDNs.** Nothing is copied or
  cached here. One that blocks the request leaves the card's neutral
  placeholder rather than a broken-image icon.
- **`events.json` does not exist until the first booking day opens.** A fresh
  install has an empty feed, and that is correct, not a failure to load.

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
- **The repo is public on purpose.** GitHub Actions minutes are free on
  public repos and limited on private ones, and this monitor's 30-minute
  cadence would run well past a private repo's free allowance. No secrets
  are stored in the repo — the Telegram token and chat ID live only as
  GitHub Actions secrets.
