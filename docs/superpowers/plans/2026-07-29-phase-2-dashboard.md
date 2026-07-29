# pop-hunt Phase 2 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static dashboard showing what is currently bookable at each tracked cinema — movies, posters and showtimes — plus a feed of recent booking-day openings, deployed to Cloudflare Pages by the existing monitor workflow.

**Architecture:** A Vite + React 19 + TanStack Router single-page app in `site/`, written in TypeScript. It is a pure static build with no server and no SSR: it fetches `data/snapshot.json` and `data/events.json` — the files Phase 1 already writes and commits — and renders them. All display logic lives in **pure, prop-driven components** that are unit-tested directly; the route modules are thin wrappers that only wire loader data to those components. The same GitHub Actions workflow that runs the monitor copies the data files into the build and deploys.

**Tech Stack:** Vite, React 19, TanStack Router (file-based routing), TypeScript, Vitest + Testing Library, Cloudflare Pages via `cloudflare/wrangler-action@v3`.

**Spec:** `docs/superpowers/specs/2026-07-29-pop-hunt-cinema-monitor-design.md` (§11 Dashboard)
**Phase 1 plan:** `docs/superpowers/plans/2026-07-29-phase-1-monitor.md`

---

## The data you are rendering — verified, not assumed

Read this before designing anything. It is taken from the real `data/snapshot.json`
produced by a live run on 2026-07-29 (339 KB, 4 targets).

```jsonc
{
  "generated_at": "2026-07-29T04:30:36+03:00",
  "targets": [
    {
      "id": "vox-moe-spiderman",
      "label": "VOX Mall of Egypt — Spider-Man: Brand New Day",
      "url": "https://egy.voxcinemas.com/showtimes?c=mall-of-egypt&m=spider-man-brand-new-day",
      "site": "vox",                    // "vox" | "scene" | "premiere"
      "scope": "movie",                 // "movie" | "cinema"
      "dates": ["2026-07-30", "…", "2026-08-05"],   // sorted ISO, the booking window
      "status": "ok",                   // "ok" | "stale" | "error"
      // "stale_since": "…"             // present ONLY on stale/error entries
      "movies": [
        {
          "title": "Spider-Man: Brand New Day",
          "poster_url": "https://assets.voxcinemas.com/heroes/B_HO00013065_….jpg",
          "rating": "12+",              // any of these five may be null
          "runtime_min": 140,
          "language": "English",
          "showtimes": {                // ISO date -> Showtime[]  (may be {} )
            "2026-07-30": [
              { "time": "10:45am", "experience": "MAX", "attributes": [], "available": false },
              { "time": "12:00pm", "experience": "Standard", "attributes": ["3D"], "available": true }
            ]
          }
        }
      ]
    }
  ]
}
```

**Four properties of this data that the UI must respect. Getting these wrong is
the main way this dashboard ends up lying to the user.**

1. **`dates` and `showtimes` keys are different sets.** `dates` is the full
   booking window. `showtimes` is only the days actually scraped. Measured
   coverage:

   | target | scope | `dates` | days with showtimes |
   |---|---|---|---|
   | `vox-moe-spiderman` | movie | 7 | **1** |
   | `vox-moe-all` | cinema | 8 | **1** |
   | `scene-district5-spiderman` | movie | 7 | 7 |
   | `premiere-cima-arkan-spiderman` | movie | 7 | 7 |

   VOX deliberately collects showtimes only for the day its page opens on (it
   rejects repeat requests from one browser context — see the Phase 1 plan).
   So a date with no entry in `showtimes` means **"not collected"**, NOT "no
   screenings". The UI must say so explicitly and must never render an empty
   list that implies a cinema is closed.

2. **`available: false` is common and meaningful** — sold out, or the showing
   already started. In the sample above every VOX time is `false` because the
   page was captured after those screenings began. Render these dimmed and
   still visible; do not hide them, or a day looks empty.

3. **`data/events.json` may not exist at all.** It is created by the first
   booking-day opening and no opening has happened yet, so `fetch` returns
   **404** today. Treat that as an empty feed, not an error.

4. **`status` is display state, distinct from anything in the monitor.** `ok` =
   rendered this run. `stale` = the render failed and this is the last good data,
   carried over, with `stale_since`. `error` = failed and nothing was ever
   captured, so `movies` is `[]`. Premiere fails roughly 1 run in 4, so `stale`
   is a normal state you will see, not an edge case.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `site/package.json` | Deps and scripts |
| `site/vite.config.ts` | Vite + TanStack Router plugin (**before** the React plugin) + Vitest config |
| `site/tsconfig.json` | TypeScript config |
| `site/index.html` | Mount point |
| `site/src/main.tsx` | Router bootstrap and `RouterProvider` |
| `site/src/globals.d.ts` | Declares `__BUILT_AT__`, injected by Vite at build |
| `site/src/types.ts` | TS mirrors of the Python data model |
| `site/src/lib/data.ts` | Memoised fetch of both JSON files; 404-tolerant |
| `site/src/lib/format.ts` | Pure date/label/grouping helpers |
| `site/src/components/StatusBadge.tsx` | `ok`/`stale`/`error` pill |
| `site/src/components/EventFeed.tsx` | Recent openings list |
| `site/src/components/TargetCard.tsx` | One target summary on the overview |
| `site/src/components/DateStrip.tsx` | Day selector, mirrors the cinemas' own strip |
| `site/src/components/MovieCard.tsx` | Poster, title, metadata, showtimes for the selected day |
| `site/src/routes/__root.tsx` | Shell: header, nav, `<Outlet/>` |
| `site/src/routes/index.tsx` | Overview: events feed + target cards |
| `site/src/routes/targets.$targetId.tsx` | One target: date strip + movies |
| `site/src/styles.css` | Theme, layout, responsive rules |
| `site/src/__fixtures__/snapshot.json` | Trimmed real snapshot for tests |
| `site/src/**/*.test.ts(x)` | Vitest tests colocated with what they test |
| `.github/workflows/monitor.yml` | **Modify**: build and deploy the dashboard |
| `README.md` | **Modify**: dashboard setup |
| `src/pop_hunt/adapters/vox.py` | **Modify** (Task 1): per-movie showtimes |

**Design rule that makes this testable:** components are pure and take plain
props — they never call `useLoaderData`, never fetch, never read the router.
Route modules do that and pass values down. So every component is unit-testable
with no router and no network, and the routes stay trivial enough not to need
their own tests.

*Deliberate deviation from spec §14*, which called for "render smoke tests for
the two routes". Testing routes means standing up a memory router and stubbing
loaders — slow, brittle, and it exercises TanStack Router more than it exercises
our code. Pushing all display logic into prop-driven components and testing
those covers strictly more behaviour for less machinery. The routes are then
thin enough that Task 6's manual `npm run dev` check is adequate coverage for
the wiring.

**Dependency order:** VOX data fix → scaffold → types → data/format libs →
components → routes → styling → deploy → docs.

---

## Task 1: Fix VOX per-movie showtime attribution

Not cosmetic, and it belongs here rather than in Phase 1 because the dashboard
is what exposes it: `vox-moe-all` currently reports 17 movies that each carry
the *same* 97 showtimes. Rendered as-is, every movie on that cinema page would
show an identical, wrong schedule.

VOX's HTML already groups showtimes inside each `<article class="movie-compare">`,
and `vox.py` already has an `_ARTICLE` regex that isolates them — so this is
attribution, not new parsing.

**Files:**
- Modify: `src/pop_hunt/adapters/vox.py`
- Modify: `tests/test_vox_adapter.py`

- [ ] **Step 1: Read the current implementation**

Run: `sed -n '1,60p' src/pop_hunt/adapters/vox.py` and read `collect` in full.
Note that `parse_movies` already iterates `_ARTICLE.findall(html)`, and that
`collect` currently builds ONE `showtimes_by_date` dict and assigns it to every
movie.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_vox_adapter.py`. The existing `tests/fixtures/vox_day.html`
has a single article; you need a two-article fixture to prove attribution, so
create `tests/fixtures/vox_two_movies.html` by copying `vox_day.html` and adding
a second `<article class="movie-compare">` with a different title and different
times. Keep the real class names.

```python
def test_parse_movies_with_showtimes_attributes_times_to_their_own_movie():
    html = (FIXTURES / "vox_two_movies.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")

    by_title = {m.title: m for m in movies}
    assert set(by_title) == {"Spider-Man: Brand New Day", "The Odyssey"}

    spidey = by_title["Spider-Man: Brand New Day"].showtimes["2026-07-30"]
    odyssey = by_title["The Odyssey"].showtimes["2026-07-30"]

    assert [s.time for s in spidey] == ["10:45am", "2:00pm", "12:00pm", "1:30pm"]
    assert [s.time for s in odyssey] == ["6:00pm", "9:30pm"]
    # The bug this guards: every movie carrying every movie's times.
    assert all(s.time not in {"6:00pm", "9:30pm"} for s in spidey)


def test_parse_movies_with_showtimes_omits_the_date_when_a_movie_has_none():
    html = (FIXTURES / "vox_two_movies.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")
    assert all(m.showtimes.get("2026-07-30") for m in movies)


def test_real_cinema_fixture_gives_each_movie_its_own_showtimes():
    """vox-moe-all has 17 movies; they must not all share one schedule."""
    html = (FIXTURES / "vox-moe-all.html").read_text()
    movies = parse_movies_with_showtimes(html, "2026-07-30")
    assert len(movies) >= 10
    schedules = [
        tuple((s.time, s.experience) for s in m.showtimes.get("2026-07-30", []))
        for m in movies
    ]
    assert len(set(schedules)) > 1, "every movie got an identical schedule"
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_vox_adapter.py -k with_showtimes -v`
Expected: FAIL — `ImportError: cannot import name 'parse_movies_with_showtimes'`

Add it to the import list at the top of the test file first if you have not.

- [ ] **Step 4: Implement**

Add to `src/pop_hunt/adapters/vox.py`, alongside the existing pure functions:

```python
def parse_movies_with_showtimes(html: str, iso_date: str) -> list[Movie]:
    """One Movie per article, each carrying only ITS OWN showtimes.

    VOX groups showtimes inside each <article class="movie-compare">, so the
    per-article fragment is the correct scope. Parsing page-wide instead gives
    every movie the whole cinema's schedule.
    """
    movies: list[Movie] = []
    for article in _ARTICLE.findall(html):
        parsed = parse_movies(article)
        if not parsed:
            continue
        showtimes = parse_showtimes(article)
        movie = parsed[0]
        movies.append(
            Movie(
                title=movie.title,
                poster_url=movie.poster_url,
                rating=movie.rating,
                runtime_min=movie.runtime_min,
                language=movie.language,
                showtimes={iso_date: showtimes} if showtimes else {},
            )
        )
    return movies
```

Then in `VoxAdapter.collect`, replace the block that assigns one shared
`showtimes_by_date` to every movie with a call to the new function for the
displayed day. Keep everything else — **do not reintroduce navigation**; the
existing docstring explains why.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/pytest tests/test_vox_adapter.py -v`
Expected: PASS, including the pre-existing `collect` tests.

- [ ] **Step 6: Run the full suite and a real run**

Run: `.venv/bin/pytest -q` → expect all green (121 + your new tests).

Run: `.venv/bin/python -m pop_hunt.main` (~95s, hits live sites), then:

```bash
.venv/bin/python -c "
import json
s = json.load(open('data/snapshot.json'))
t = next(x for x in s['targets'] if x['id'] == 'vox-moe-all')
scheds = {tuple((v['time'], v['experience']) for v in sum(m['showtimes'].values(), [])) for m in t['movies']}
print(f\"movies={len(t['movies'])} distinct_schedules={len(scheds)}\")
"
```
Expected: `distinct_schedules` well above 1. If it is 1, attribution is still wrong.

- [ ] **Step 7: Commit**

```bash
git add src/pop_hunt/adapters/vox.py tests/test_vox_adapter.py tests/fixtures/vox_two_movies.html data state.json
git commit -m "fix: attribute vox showtimes to their own movie"
```

---

## Task 2: Scaffold the Vite + React 19 + TanStack Router app

**Files:** Create `site/package.json`, `site/tsconfig.json`, `site/vite.config.ts`, `site/index.html`, `site/.gitignore`

- [ ] **Step 1: Create `site/package.json`**

```json
{
  "name": "pop-hunt-dashboard",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@tanstack/react-router": "^1.95.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@tanstack/router-plugin": "^1.95.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Create `site/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noEmit": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `site/vite.config.ts`**

The plugin order matters — `tanstackRouter` must come **before** `react()`.

```ts
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    // Must be registered BEFORE the react plugin.
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
  define: {
    // Baked in at build time. The workflow deploys on EVERY monitor run, but
    // the repo is only committed to when data actually changes - so without
    // this the header would read "Data as of yesterday" on a quiet day and
    // look broken. This is what proves the monitor is still alive.
    __BUILT_AT__: JSON.stringify(new Date().toISOString()),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
```

Declare the global for TypeScript — create `site/src/globals.d.ts`:

```ts
/** Injected by Vite at build time; see `define` in vite.config.ts. */
declare const __BUILT_AT__: string
```

- [ ] **Step 4: Create `site/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="dark light" />
    <title>pop-hunt</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `site/src/test-setup.ts`**

```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 6: Create `site/.gitignore`**

```
node_modules/
dist/
public/data/
*.tsbuildinfo
```

`public/data/` is copied in at build time, so it is not committed.

**`src/routeTree.gen.ts` IS committed** — deliberately. It is generated by the
router plugin, but `build` runs `tsc -b` *before* `vite build`, so on a clean
checkout nothing has generated it yet and the type check fails with a cascade of
errors. Committing it makes a fresh clone and CI build with no extra tooling,
and it fails loudly (a `tsc` error in CI) if someone adds a route and forgets to
regenerate — which is the failure you want. The alternatives are worse: adding
`@tanstack/router-cli` duplicates what the plugin already does, and reordering to
`vite build && tsc -b` would stop type errors blocking the build.

- [ ] **Step 7: Install and verify the toolchain**

```bash
cd site && npm install
```
Expected: completes without peer-dependency errors. If React 19 causes a peer
conflict with any package, report it rather than forcing `--legacy-peer-deps`.

- [ ] **Step 8: Commit**

```bash
git add site
git commit -m "chore: scaffold the dashboard app"
```

---

## Task 3: Types and the data layer

**Files:** Create `site/src/types.ts`, `site/src/lib/data.ts`, `site/src/__fixtures__/snapshot.json`, `site/src/lib/data.test.ts`

- [ ] **Step 1: Create the test fixture from real data**

The real file is 339 KB — far too big for a test. Trim it to two targets and at
most two movies each, keeping the exact shape:

```bash
.venv/bin/python - <<'PY'
import json, pathlib
s = json.load(open("data/snapshot.json"))
keep = {"vox-moe-spiderman", "scene-district5-spiderman"}
out = {
    "generated_at": s["generated_at"],
    "targets": [
        {**t, "movies": [
            {**m, "showtimes": {d: v[:3] for d, v in list(m["showtimes"].items())[:2]}}
            for m in t["movies"][:2]
        ]}
        for t in s["targets"] if t["id"] in keep
    ],
}
p = pathlib.Path("site/src/__fixtures__/snapshot.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print("targets:", [t["id"] for t in out["targets"]], "size:", p.stat().st_size)
PY
```
Expected: two targets, a few KB. **Read the result** and confirm it still has a
target with `dates` longer than its `showtimes` keys — that asymmetry is what
several tests depend on.

- [ ] **Step 2: Create `site/src/types.ts`**

```ts
/** Mirrors the Python dataclasses in src/pop_hunt/models.py. */

export type TargetStatus = 'ok' | 'stale' | 'error'
export type SiteId = 'vox' | 'scene' | 'premiere'
export type Scope = 'movie' | 'cinema'

export interface Showtime {
  time: string
  experience: string | null
  attributes: string[]
  /** False when sold out or already started. Render dimmed, never hidden. */
  available: boolean
}

export interface Movie {
  title: string
  poster_url: string | null
  rating: string | null
  runtime_min: number | null
  language: string | null
  /** ISO date -> showtimes. A MISSING key means "not collected", not "closed". */
  showtimes: Record<string, Showtime[]>
}

export interface TargetEntry {
  id: string
  label: string
  url: string
  site: SiteId
  scope: Scope
  /** The full booking window. A superset of the showtimes keys. */
  dates: string[]
  movies: Movie[]
  status: TargetStatus
  stale_since?: string
}

export interface Snapshot {
  generated_at: string | null
  targets: TargetEntry[]
}

export interface OpeningEvent {
  at: string
  target_id: string
  label: string
  previous: string | null
  new_max: string
  added: string[]
  url: string
}

export interface Dashboard {
  snapshot: Snapshot
  events: OpeningEvent[]
}
```

- [ ] **Step 3: Write the failing test** — `site/src/lib/data.test.ts`

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { __resetDashboardCache, loadDashboard } from './data'
import snapshotFixture from '../__fixtures__/snapshot.json'

function mockFetch(handlers: Record<string, () => Response>) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const key = Object.keys(handlers).find((k) => url.includes(k))
    return Promise.resolve(key ? handlers[key]() : new Response('', { status: 404 }))
  })
}

const okSnapshot = () => new Response(JSON.stringify(snapshotFixture), { status: 200 })
const okEvents = () =>
  new Response(JSON.stringify([{ at: 't1', target_id: 'a', label: 'A', previous: null, new_max: '2026-08-06', added: ['2026-08-06'], url: 'u' }]), { status: 200 })

describe('loadDashboard', () => {
  beforeEach(() => __resetDashboardCache())

  it('loads the snapshot and events together', async () => {
    vi.stubGlobal('fetch', mockFetch({ 'snapshot.json': okSnapshot, 'events.json': okEvents }))
    const { snapshot, events } = await loadDashboard()
    expect(snapshot.targets.length).toBeGreaterThan(0)
    expect(events).toHaveLength(1)
  })

  it('treats a missing events file as an empty feed', async () => {
    // events.json does not exist until the first booking day opens -> 404.
    vi.stubGlobal('fetch', mockFetch({ 'snapshot.json': okSnapshot }))
    const { events } = await loadDashboard()
    expect(events).toEqual([])
  })

  it('yields an empty dashboard rather than throwing when the snapshot is missing', async () => {
    vi.stubGlobal('fetch', mockFetch({}))
    const { snapshot, events } = await loadDashboard()
    expect(snapshot.targets).toEqual([])
    expect(snapshot.generated_at).toBeNull()
    expect(events).toEqual([])
  })

  it('fetches only once across repeated calls', async () => {
    const fetchMock = mockFetch({ 'snapshot.json': okSnapshot, 'events.json': okEvents })
    vi.stubGlobal('fetch', fetchMock)
    await loadDashboard()
    await loadDashboard()
    expect(fetchMock).toHaveBeenCalledTimes(2) // snapshot + events, not four
  })
})
```

- [ ] **Step 4: Run to verify it fails**

Run: `cd site && npx vitest run src/lib/data.test.ts`
Expected: FAIL — cannot resolve `./data`.

- [ ] **Step 5: Implement** — `site/src/lib/data.ts`

```ts
import type { Dashboard, OpeningEvent, Snapshot } from '../types'

const SNAPSHOT_URL = '/data/snapshot.json'
const EVENTS_URL = '/data/events.json'

const EMPTY_SNAPSHOT: Snapshot = { generated_at: null, targets: [] }

/**
 * Fetch JSON, or fall back when it is missing.
 *
 * `events.json` legitimately does not exist until the first booking day opens,
 * so a 404 is an expected state and must not surface as an error.
 */
async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url)
    if (!response.ok) return fallback
    return (await response.json()) as T
  } catch {
    return fallback
  }
}

let cache: Promise<Dashboard> | null = null

/** Both data files, fetched once per page load and shared by every route. */
export function loadDashboard(): Promise<Dashboard> {
  cache ??= Promise.all([
    fetchJson<Snapshot>(SNAPSHOT_URL, EMPTY_SNAPSHOT),
    fetchJson<OpeningEvent[]>(EVENTS_URL, []),
  ]).then(([snapshot, events]) => ({ snapshot, events }))
  return cache
}

/** Test seam - route loaders must never need this. */
export function __resetDashboardCache(): void {
  cache = null
}
```

- [ ] **Step 6: Run the tests**

Run: `cd site && npx vitest run src/lib/data.test.ts`
Expected: PASS — 4 passed.

- [ ] **Step 7: Commit**

```bash
git add site/src/types.ts site/src/lib/data.ts site/src/lib/data.test.ts site/src/__fixtures__
git commit -m "feat: add dashboard types and data layer"
```

---

## Task 4: Pure formatting helpers

Everything here is pure, so it is where the data's sharp edges get handled once.

**Files:** Create `site/src/lib/format.ts`, `site/src/lib/format.test.ts`

- [ ] **Step 1: Write the failing test** — `site/src/lib/format.test.ts`

```ts
import { describe, expect, it } from 'vitest'
import type { Movie, TargetEntry } from '../types'
import {
  bookingWindowLabel,
  dayLabel,
  formatGeneratedAt,
  groupByExperience,
  hasCollectedShowtimes,
  showtimesFor,
} from './format'

const movie: Movie = {
  title: 'A Film',
  poster_url: null,
  rating: null,
  runtime_min: null,
  language: null,
  showtimes: {
    '2026-07-30': [
      { time: '10:45am', experience: 'MAX', attributes: [], available: false },
      { time: '2:00pm', experience: 'MAX', attributes: [], available: true },
      { time: '12:00pm', experience: 'Standard', attributes: ['3D'], available: true },
    ],
  },
}

const target: TargetEntry = {
  id: 't', label: 'T', url: 'u', site: 'vox', scope: 'movie',
  dates: ['2026-07-30', '2026-07-31', '2026-08-05'],
  movies: [movie], status: 'ok',
}

describe('dayLabel', () => {
  it('renders a short human day', () => {
    expect(dayLabel('2026-07-30')).toBe('Thu 30 Jul')
  })

  it('does not shift the day across timezones', () => {
    // Parsing "2026-01-01" as UTC then rendering locally can yield 31 Dec.
    expect(dayLabel('2026-01-01')).toBe('Thu 1 Jan')
  })
})

describe('bookingWindowLabel', () => {
  it('reports the furthest bookable date', () => {
    expect(bookingWindowLabel(target)).toBe('Booking through Wed 5 Aug')
  })

  it('handles a target with no dates', () => {
    expect(bookingWindowLabel({ ...target, dates: [] })).toBe('No dates available')
  })
})

describe('showtimesFor / hasCollectedShowtimes', () => {
  it('returns the times for a collected day', () => {
    expect(showtimesFor(movie, '2026-07-30')).toHaveLength(3)
    expect(hasCollectedShowtimes(movie, '2026-07-30')).toBe(true)
  })

  it('distinguishes "not collected" from "no screenings"', () => {
    // VOX collects showtimes for one day only; the rest are unknown, not empty.
    expect(showtimesFor(movie, '2026-08-05')).toEqual([])
    expect(hasCollectedShowtimes(movie, '2026-08-05')).toBe(false)
  })
})

describe('groupByExperience', () => {
  it('groups times under their experience, preserving order', () => {
    const groups = groupByExperience(showtimesFor(movie, '2026-07-30'))
    expect(groups.map((g) => g.experience)).toEqual(['MAX', 'Standard'])
    expect(groups[0].showtimes.map((s) => s.time)).toEqual(['10:45am', '2:00pm'])
  })

  it('labels ungrouped times rather than dropping them', () => {
    const groups = groupByExperience([
      { time: '7:00pm', experience: null, attributes: [], available: true },
    ])
    expect(groups).toHaveLength(1)
    expect(groups[0].experience).toBe('Standard')
  })
})

describe('formatGeneratedAt', () => {
  it('renders a readable timestamp', () => {
    expect(formatGeneratedAt('2026-07-29T04:30:36+03:00')).toContain('29 Jul')
  })

  it('handles never-generated data', () => {
    expect(formatGeneratedAt(null)).toBe('never')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd site && npx vitest run src/lib/format.test.ts`
Expected: FAIL — cannot resolve `./format`.

- [ ] **Step 3: Implement** — `site/src/lib/format.ts`

```ts
import type { Movie, Showtime, TargetEntry } from '../types'

export interface ExperienceGroup {
  experience: string
  showtimes: Showtime[]
}

/**
 * Parse an ISO date as LOCAL midnight.
 *
 * `new Date('2026-01-01')` parses as UTC, so in a negative-offset timezone it
 * renders as 31 Dec. Splitting the parts avoids that entirely.
 */
function localDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function dayLabel(iso: string): string {
  return localDate(iso).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

export function bookingWindowLabel(target: TargetEntry): string {
  if (target.dates.length === 0) return 'No dates available'
  const furthest = target.dates[target.dates.length - 1]
  return `Booking through ${dayLabel(furthest)}`
}

/** Showtimes for a day, or [] when that day was never collected. */
export function showtimesFor(movie: Movie, iso: string): Showtime[] {
  return movie.showtimes[iso] ?? []
}

/**
 * Whether this day's showtimes were actually scraped.
 *
 * VOX collects only the day its page opens on, so most days are unknown. The UI
 * must not present unknown as "no screenings".
 */
export function hasCollectedShowtimes(movie: Movie, iso: string): boolean {
  return Object.prototype.hasOwnProperty.call(movie.showtimes, iso)
}

export function groupByExperience(showtimes: Showtime[]): ExperienceGroup[] {
  const groups: ExperienceGroup[] = []
  for (const showtime of showtimes) {
    const experience = showtime.experience ?? 'Standard'
    const existing = groups.find((g) => g.experience === experience)
    if (existing) existing.showtimes.push(showtime)
    else groups.push({ experience, showtimes: [showtime] })
  }
  return groups
}

export function formatGeneratedAt(iso: string | null): string {
  if (!iso) return 'never'
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
```

- [ ] **Step 4: Run the tests**

Run: `cd site && npx vitest run src/lib/format.test.ts`
Expected: PASS — 10 passed.

- [ ] **Step 5: Commit**

```bash
git add site/src/lib/format.ts site/src/lib/format.test.ts
git commit -m "feat: add dashboard formatting helpers"
```

---

## Task 5: Presentational components

All pure and prop-driven. This is the bulk of the UI and all of its tests.

**Files:** Create `site/src/components/{StatusBadge,EventFeed,TargetCard,DateStrip,MovieCard}.tsx` and a `.test.tsx` beside each.

- [ ] **Step 1: Write `StatusBadge` test and component**

```tsx
// site/src/components/StatusBadge.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { formatGeneratedAt } from '../lib/format'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders nothing when the target is healthy', () => {
    const { container } = render(<StatusBadge status="ok" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('explains stale data and when it went stale', () => {
    // Derive the expected wall clock rather than hardcoding one: the suite runs
    // at a pinned negative offset, where this instant renders as 28 Jul.
    const staleSince = '2026-07-29T04:30:36+03:00'
    const expected = formatGeneratedAt(staleSince)
    render(<StatusBadge status="stale" staleSince={staleSince} />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(expected))).toBeInTheDocument()
  })

  it('flags an error state', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument()
  })
})
```

```tsx
// site/src/components/StatusBadge.tsx
import { formatGeneratedAt } from '../lib/format'
import type { TargetStatus } from '../types'

/** Silent when healthy - a badge on every card would be noise. */
export function StatusBadge({
  status,
  staleSince,
}: {
  status: TargetStatus
  staleSince?: string
}) {
  if (status === 'ok') return null
  if (status === 'error') {
    return <span className="badge badge--error">Unavailable</span>
  }
  return (
    <span className="badge badge--stale">
      Stale since {formatGeneratedAt(staleSince ?? null)}
    </span>
  )
}
```

Run: `cd site && npx vitest run src/components/StatusBadge.test.tsx` → 3 passed.

- [ ] **Step 2: Write `EventFeed` test and component**

```tsx
// site/src/components/EventFeed.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EventFeed } from './EventFeed'
import type { OpeningEvent } from '../types'

const event: OpeningEvent = {
  at: '2026-07-30T09:03:00+03:00',
  target_id: 'scene-district5-spiderman',
  label: 'Scene District 5 — Spider-Man',
  previous: '2026-08-05',
  new_max: '2026-08-06',
  added: ['2026-08-06'],
  url: 'https://example.test',
}

describe('EventFeed', () => {
  it('tells the user what opened', () => {
    render(<EventFeed events={[event]} />)
    expect(screen.getByText(/Scene District 5/)).toBeInTheDocument()
    expect(screen.getByText(/Thu 6 Aug/)).toBeInTheDocument()
  })

  it('lists every added date', () => {
    render(<EventFeed events={[{ ...event, added: ['2026-08-06', '2026-08-07'] }]} />)
    expect(screen.getByText(/Thu 6 Aug/)).toBeInTheDocument()
    expect(screen.getByText(/Fri 7 Aug/)).toBeInTheDocument()
  })

  it('says so plainly when nothing has opened yet', () => {
    render(<EventFeed events={[]} />)
    expect(screen.getByText(/no openings recorded yet/i)).toBeInTheDocument()
  })
})
```

```tsx
// site/src/components/EventFeed.tsx
import { dayLabel, formatGeneratedAt } from '../lib/format'
import type { OpeningEvent } from '../types'

/** `events.json` is already stored newest-first - do not re-sort it. */
export function EventFeed({ events }: { events: OpeningEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="empty">
        No openings recorded yet. When a cinema opens a new bookable day it will
        appear here, and you will get a Telegram alert.
      </p>
    )
  }

  return (
    <ol className="feed">
      {events.map((event) => (
        <li key={`${event.target_id}-${event.at}`} className="feed__item">
          <p className="feed__label">{event.label}</p>
          <p className="feed__dates">
            Opened{' '}
            {event.added.map((iso, index) => (
              <span key={iso}>
                {index > 0 && ', '}
                <strong>{dayLabel(iso)}</strong>
              </span>
            ))}
          </p>
          <p className="feed__meta">{formatGeneratedAt(event.at)}</p>
        </li>
      ))}
    </ol>
  )
}
```

Run its test → 3 passed.

- [ ] **Step 3: Write `DateStrip` test and component**

```tsx
// site/src/components/DateStrip.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DateStrip } from './DateStrip'

const dates = ['2026-07-30', '2026-07-31', '2026-08-01']

describe('DateStrip', () => {
  it('renders one control per bookable date', () => {
    render(<DateStrip dates={dates} selected="2026-07-30" onSelect={() => {}} />)
    expect(screen.getAllByRole('button')).toHaveLength(3)
  })

  it('marks the selected day for assistive tech, not just visually', () => {
    render(<DateStrip dates={dates} selected="2026-07-31" onSelect={() => {}} />)
    expect(screen.getByRole('button', { name: /31 Jul/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /30 Jul/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('reports the chosen day', async () => {
    const onSelect = vi.fn()
    render(<DateStrip dates={dates} selected="2026-07-30" onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('button', { name: /1 Aug/ }))
    expect(onSelect).toHaveBeenCalledWith('2026-08-01')
  })
})
```

```tsx
// site/src/components/DateStrip.tsx
import { dayLabel } from '../lib/format'

/** Mirrors the date strip the cinemas themselves use. */
export function DateStrip({
  dates,
  selected,
  onSelect,
}: {
  dates: string[]
  selected: string
  onSelect: (iso: string) => void
}) {
  return (
    <div className="strip" role="group" aria-label="Choose a day">
      {dates.map((iso) => (
        <button
          key={iso}
          type="button"
          // aria-pressed, not just a class: the selection must be conveyed to
          // assistive tech, not only to sighted users.
          aria-pressed={iso === selected}
          className={
            iso === selected ? 'strip__day strip__day--selected' : 'strip__day'
          }
          onClick={() => onSelect(iso)}
        >
          {dayLabel(iso)}
        </button>
      ))}
    </div>
  )
}
```

Run its test → 3 passed.

- [ ] **Step 4: Write `MovieCard` test and component**

This is where the "not collected" distinction from the data notes must land.

```tsx
// site/src/components/MovieCard.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MovieCard } from './MovieCard'
import type { Movie } from '../types'

const movie: Movie = {
  title: 'Spider-Man: Brand New Day',
  poster_url: 'https://example.test/p.jpg',
  rating: '12+',
  runtime_min: 140,
  language: 'English',
  showtimes: {
    '2026-07-30': [
      { time: '10:45am', experience: 'MAX', attributes: [], available: false },
      { time: '2:00pm', experience: 'MAX', attributes: ['3D'], available: true },
    ],
  },
}

describe('MovieCard', () => {
  it('shows the title and metadata', () => {
    render(<MovieCard movie={movie} date="2026-07-30" />)
    expect(screen.getByText(movie.title)).toBeInTheDocument()
    expect(screen.getByText(/12\+/)).toBeInTheDocument()
    expect(screen.getByText(/140 min/)).toBeInTheDocument()
    expect(screen.getByText(/English/)).toBeInTheDocument()
  })

  it('renders the poster without leaking a referrer', () => {
    render(<MovieCard movie={movie} date="2026-07-30" />)
    const img = screen.getByRole('img', { name: movie.title })
    expect(img).toHaveAttribute('referrerpolicy', 'no-referrer')
    expect(img).toHaveAttribute('loading', 'lazy')
  })

  it('shows sold-out times dimmed rather than hiding them', () => {
    render(<MovieCard movie={movie} date="2026-07-30" />)
    expect(screen.getByText('10:45am')).toHaveClass('showtime--unavailable')
    expect(screen.getByText('2:00pm')).not.toHaveClass('showtime--unavailable')
  })

  it('labels attributes like 3D', () => {
    render(<MovieCard movie={movie} date="2026-07-30" />)
    expect(screen.getByText('3D')).toBeInTheDocument()
  })

  it('says showtimes were not collected rather than implying none exist', () => {
    render(<MovieCard movie={movie} date="2026-08-05" />)
    expect(screen.getByText(/not collected/i)).toBeInTheDocument()
    expect(screen.queryByText(/no screenings/i)).not.toBeInTheDocument()
  })

  it('copes with entirely missing metadata', () => {
    const bare: Movie = { ...movie, poster_url: null, rating: null, runtime_min: null, language: null }
    render(<MovieCard movie={bare} date="2026-07-30" />)
    expect(screen.getByText(bare.title)).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
```

```tsx
// site/src/components/MovieCard.tsx
import { groupByExperience, hasCollectedShowtimes, showtimesFor } from '../lib/format'
import type { Movie } from '../types'

export function MovieCard({ movie, date }: { movie: Movie; date: string }) {
  const meta = [movie.rating, movie.language, movie.runtime_min ? `${movie.runtime_min} min` : null]
    .filter(Boolean)
    .join(' · ')

  return (
    <article className="movie">
      {movie.poster_url && (
        <img
          className="movie__poster"
          src={movie.poster_url}
          alt={movie.title}
          // Hot-linked from the cinema's CDN. no-referrer avoids leaking where
          // the request came from and dodges naive hot-link blocking; a failure
          // leaves the styled background, never a broken-image icon.
          referrerPolicy="no-referrer"
          loading="lazy"
        />
      )}
      <div className="movie__body">
        <h3 className="movie__title">{movie.title}</h3>
        {meta && <p className="movie__meta">{meta}</p>}
        <Showtimes movie={movie} date={date} />
      </div>
    </article>
  )
}

function Showtimes({ movie, date }: { movie: Movie; date: string }) {
  // "Not collected" and "no screenings" are genuinely different things here.
  // VOX only scrapes the day its page opens on, so most days are unknown -
  // rendering an empty list would claim the cinema is shut.
  if (!hasCollectedShowtimes(movie, date)) {
    return <p className="movie__note">Showtimes not collected for this day.</p>
  }

  const groups = groupByExperience(showtimesFor(movie, date))
  if (groups.length === 0) {
    return <p className="movie__note">No screenings on this day.</p>
  }

  return (
    <div className="showtimes">
      {groups.map((group) => (
        <div key={group.experience} className="showtimes__group">
          <p className="showtimes__experience">{group.experience}</p>
          <ul className="showtimes__list">
            {group.showtimes.map((showtime, index) => (
              <li key={`${showtime.time}-${index}`}>
                {/* Sold out and already-started times stay visible but dimmed;
                    hiding them makes a busy day look empty. */}
                <span
                  className={
                    showtime.available ? 'showtime' : 'showtime showtime--unavailable'
                  }
                >
                  {showtime.time}
                </span>
                {showtime.attributes.map((attribute) => (
                  <span key={attribute} className="tag">
                    {attribute}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
```

Run its test → 6 passed.

- [ ] **Step 5: Write `TargetCard` test and component**

```tsx
// site/src/components/TargetCard.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TargetCard } from './TargetCard'
import type { TargetEntry } from '../types'

const target: TargetEntry = {
  id: 'vox-moe-spiderman',
  label: 'VOX Mall of Egypt — Spider-Man',
  url: 'https://example.test',
  site: 'vox',
  scope: 'movie',
  dates: ['2026-07-30', '2026-08-05'],
  movies: [],
  status: 'ok',
}

describe('TargetCard', () => {
  it('shows the label and booking window', () => {
    render(<TargetCard target={target} />)
    expect(screen.getByText(target.label)).toBeInTheDocument()
    expect(screen.getByText(/Booking through Wed 5 Aug/)).toBeInTheDocument()
  })

  it('surfaces a stale badge', () => {
    render(<TargetCard target={{ ...target, status: 'stale', stale_since: '2026-07-29T04:30:36+03:00' }} />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
  })

  it('links to the cinema booking page', () => {
    render(<TargetCard target={target} />)
    const link = screen.getByRole('link', { name: /book/i })
    expect(link).toHaveAttribute('href', target.url)
    expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
  })
})
```

```tsx
// site/src/components/TargetCard.tsx
import type { ReactNode } from 'react'
import { bookingWindowLabel } from '../lib/format'
import type { TargetEntry } from '../types'
import { StatusBadge } from './StatusBadge'

/**
 * Router-free by design: the internal detail link arrives as `children` so this
 * stays a pure component that renders without a router in tests.
 */
export function TargetCard({
  target,
  children,
}: {
  target: TargetEntry
  children?: ReactNode
}) {
  return (
    <article className="card">
      <header className="card__header">
        <h3 className="card__title">{target.label}</h3>
        <StatusBadge status={target.status} staleSince={target.stale_since} />
      </header>
      <p className="card__window">{bookingWindowLabel(target)}</p>
      <footer className="card__actions">
        {children}
        <a
          className="button button--ghost"
          href={target.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Book at cinema
        </a>
      </footer>
    </article>
  )
}
```

Run its test → 3 passed.

- [ ] **Step 6: Run all component tests and commit**

Run: `cd site && npx vitest run`
Expected: all green.

```bash
git add site/src/components
git commit -m "feat: add dashboard components"
```

---

## Task 6: Routes

Thin wrappers. They read loader data and the search param, and hand plain values
to the components built in Task 5.

**Files:** Create `site/src/main.tsx`, `site/src/routes/__root.tsx`, `site/src/routes/index.tsx`, `site/src/routes/targets.$targetId.tsx`

- [ ] **Step 1: Create `site/src/main.tsx`**

```tsx
import { RouterProvider, createRouter } from '@tanstack/react-router'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { routeTree } from './routeTree.gen'
import './styles.css'

const router = createRouter({ routeTree, defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById('app')!
ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
```

`routeTree.gen.ts` does not exist yet — the router plugin generates it on the
first `vite dev` or `vite build`. TypeScript will complain until then; that is
expected.

- [ ] **Step 2: Create `site/src/routes/__root.tsx`**

```tsx
import { Link, Outlet, createRootRoute } from '@tanstack/react-router'
import { loadDashboard } from '../lib/data'
import { formatGeneratedAt } from '../lib/format'

export const Route = createRootRoute({
  loader: () => loadDashboard(),
  component: RootLayout,
})

function RootLayout() {
  const { snapshot } = Route.useLoaderData()
  return (
    <div className="app">
      <header className="app__header">
        <Link to="/" className="app__brand">
          pop&#8209;hunt
        </Link>
        {/* Two different timestamps, deliberately. "Last checked" proves the
            monitor ran; "data as of" is when anything last changed. On a quiet
            day they differ by hours, and showing only the latter looks broken. */}
        <p className="app__meta">
          <span>Last checked {formatGeneratedAt(__BUILT_AT__)}</span>
          <span>Data as of {formatGeneratedAt(snapshot.generated_at)}</span>
        </p>
      </header>
      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Create `site/src/routes/index.tsx`**

```tsx
import { Link, createFileRoute } from '@tanstack/react-router'
import { EventFeed } from '../components/EventFeed'
import { TargetCard } from '../components/TargetCard'
import { loadDashboard } from '../lib/data'

export const Route = createFileRoute('/')({
  loader: () => loadDashboard(),
  component: Overview,
})

function Overview() {
  const { snapshot, events } = Route.useLoaderData()
  return (
    <>
      <section className="section">
        <h2 className="section__title">Recent openings</h2>
        <EventFeed events={events} />
      </section>
      <section className="section">
        <h2 className="section__title">Tracked cinemas</h2>
        <div className="grid">
          {snapshot.targets.map((target) => (
            <TargetCard key={target.id} target={target}>
              <Link to="/targets/$targetId" params={{ targetId: target.id }} className="button">
                View showtimes
              </Link>
            </TargetCard>
          ))}
        </div>
      </section>
    </>
  )
}
```

- [ ] **Step 4: Create `site/src/routes/targets.$targetId.tsx`**

The `?date=` search param is validated inline — no schema library needed for one
optional ISO string.

```tsx
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { DateStrip } from '../components/DateStrip'
import { MovieCard } from '../components/MovieCard'
import { StatusBadge } from '../components/StatusBadge'
import { loadDashboard } from '../lib/data'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export const Route = createFileRoute('/targets/$targetId')({
  validateSearch: (search: Record<string, unknown>): { date?: string } => {
    const date = search.date
    return typeof date === 'string' && ISO_DATE.test(date) ? { date } : {}
  },
  loader: () => loadDashboard(),
  component: TargetDetail,
})

function TargetDetail() {
  const { targetId } = Route.useParams()
  const { date } = Route.useSearch()
  const { snapshot } = Route.useLoaderData()
  const navigate = useNavigate({ from: Route.fullPath })

  const target = snapshot.targets.find((t) => t.id === targetId)
  if (!target) {
    return (
      <p className="empty">
        No such target. <Link to="/">Back to overview</Link>
      </p>
    )
  }

  // Default to the first bookable day; the param makes a day linkable.
  const selected = date && target.dates.includes(date) ? date : target.dates[0]

  return (
    <section className="section">
      <header className="detail__header">
        <h2 className="section__title">{target.label}</h2>
        <StatusBadge status={target.status} staleSince={target.stale_since} />
      </header>

      {target.dates.length === 0 ? (
        <p className="empty">No bookable dates were found for this target.</p>
      ) : (
        <>
          <DateStrip
            dates={target.dates}
            selected={selected}
            onSelect={(next) =>
              navigate({ search: { date: next }, replace: true })
            }
          />
          <div className="grid">
            {target.movies.map((movie, index) => (
              // Composite key: two distinct movies can share a title -
              // vox-moe-all carries both the Arabic-dub and English cuts of
              // Toy Story 5 - and the source data has no id. The list is never
              // reordered, so the index is stable.
              <MovieCard
                key={`${movie.title}-${index}`}
                movie={movie}
                date={selected}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
```

- [ ] **Step 5: Build and check it actually runs**

```bash
cd site && npm run build
```
Expected: `routeTree.gen.ts` is generated, `tsc -b` passes, and `dist/` is
written with no errors. Fix any type errors rather than loosening `strict`.

Then, to look at it with real data:

```bash
mkdir -p site/public/data && cp data/*.json site/public/data/ 2>/dev/null; cd site && npm run dev
```
Open the printed URL. Confirm by eye: the overview lists 4 targets with booking
windows, the empty events feed explains itself, clicking through to a VOX target
shows the date strip, and selecting a day other than the first shows the
"not collected" note rather than an empty schedule.

- [ ] **Step 6: Run the whole suite and commit**

Run: `cd site && npx vitest run` → all green.

```bash
git add site/src/main.tsx site/src/routes
git commit -m "feat: add dashboard routes"
```

---

## Task 7: Styling

**Files:** Create `site/src/styles.css`

- [ ] **Step 1: Load the design skill**

Invoke the `frontend-design` skill before writing CSS, and follow it. This is a
dark, poster-led cinema dashboard read mostly on a phone — favour a real visual
point of view over a generic card grid.

- [ ] **Step 2: Write the stylesheet**

Non-negotiables, because tests or data depend on them:

- `.showtime--unavailable` must be visibly dimmed but still legible (that is the
  sold-out/past state, and it is the majority state for VOX).
- Posters vary wildly in aspect ratio across the three chains — constrain with
  `aspect-ratio` and `object-fit: cover`, and give `img` a background so a failed
  hot-link (blocked referrer) leaves a neutral block, not a broken-image icon.
- The date strip must scroll horizontally on narrow screens without the page
  scrolling sideways (`overflow-x: auto` on the strip, never on `body`).
- Respect `prefers-reduced-motion`.
- Support light and dark via `prefers-color-scheme`; the page is read outdoors.

- [ ] **Step 3: Verify responsively**

Run `npm run dev` and check at 375 px and 1280 px wide. Confirm no horizontal
page scroll at 375 px.

- [ ] **Step 4: Commit**

```bash
git add site/src/styles.css
git commit -m "feat: style the dashboard"
```

---

## Task 8: Build and deploy from the workflow

**Files:** Modify `.github/workflows/monitor.yml`

- [ ] **Step 1: Add the build and deploy steps**

Append to the `check` job, after the existing "Commit data if it changed" step:

```yaml
      - name: Stage dashboard data
        run: |
          mkdir -p site/public/data
          cp data/snapshot.json site/public/data/ 2>/dev/null || true
          cp data/events.json  site/public/data/ 2>/dev/null || true

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: site/package-lock.json

      - name: Build dashboard
        working-directory: site
        run: |
          npm ci
          npm run build

      - name: Deploy dashboard
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy site/dist --project-name=pop-hunt
```

The `|| true` on the copies is deliberate: `data/events.json` does not exist
until the first booking day opens, and a missing file must not fail the run.

- [ ] **Step 2: Add the required permission**

Change the `permissions:` block to:

```yaml
permissions:
  contents: write
  deployments: write
```

- [ ] **Step 3: Commit the lockfile**

`npm ci` requires `site/package-lock.json` to be committed. Confirm it exists
(it is created by `npm install` in Task 2) and is NOT covered by
`site/.gitignore`.

Run: `git check-ignore -v site/package-lock.json || echo "tracked - good"`

- [ ] **Step 4: Validate the YAML**

Run: `.venv/bin/python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/monitor.yml').read_text()); print('valid')"`
Expected: `valid`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/monitor.yml site/package-lock.json
git commit -m "ci: build and deploy the dashboard"
```

---

## Task 9: README and final verification

**Files:** Modify `README.md`

- [ ] **Step 1: Document the dashboard**

Add a **Dashboard** section covering:
- what it shows (booking window and status per cinema, movies with posters and
  showtimes for a chosen day, plus a feed of recent openings);
- that it deploys to Cloudflare Pages on every monitor run;
- the Cloudflare setup: create a free account, create a Pages project named
  `pop-hunt` using **Direct Upload** (not a Git connection), create an API token
  with the **Cloudflare Pages: Edit** permission, then add `CLOUDFLARE_API_TOKEN`
  and `CLOUDFLARE_ACCOUNT_ID` as Actions secrets;
- local development: `cd site && npm install && npm run dev`, and that you need
  `cp data/*.json site/public/data/` first to see real data;
- **the honest caveat**: VOX showtimes are collected for one day only, so other
  days show "not collected"; Premiere fails roughly 1 run in 4 and will
  occasionally show a stale badge.

- [ ] **Step 2: Full verification**

```bash
.venv/bin/pytest -q          # Python suite, all green
cd site && npx vitest run    # dashboard suite, all green
cd site && npm run build     # type-checks and builds clean
```

- [ ] **Step 3: Confirm the built site works from the build output**

```bash
cd site && npm run preview
```
Open the URL and click through both routes. This catches anything that only
works under the dev server.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the dashboard"
```

---

## Known limitations to carry forward

- **VOX shows one day of showtimes.** Detection is unaffected. Collecting the
  rest needs a fresh browser context per date (VOX rejects repeat requests from
  one context), which would add roughly 5s per date per target.
- **Premiere is currently failing far more than the recorded 1-in-4** — observed
  5 consecutive failures on 2026-07-29 afternoon. Diagnosis: their page renders
  only the "similar movies" section and footer; the movie hero and the cinema
  chooser never paint, so `get_by_role('button', name='Cima Arkan')` finds
  nothing. The `get-movie-show-dates` API still returns 200, so the data is
  fetched and the SPA simply fails to render it. This is a fault on their side,
  not in the adapter, which correctly reports no dates rather than guessing.
  Expect a persistent stale card for that target until Premiere's site
  recovers. If it does not, the adapter may be worth a reload-and-retry, since
  the symptom is a partial render rather than an outright block.
- **`snapshot.json` is ~339 KB** and is fetched whole on first load. Fine now;
  if targets multiply, split it per target or trim showtimes from the overview
  payload.
- **Posters are hot-linked** from the cinemas' CDNs. A chain that blocks
  hot-linking leaves a neutral placeholder — by design, never a broken page.

## Done when

- Both suites pass and `npm run build` type-checks clean.
- The overview shows all four targets with correct booking windows.
- A VOX target shows "not collected" for uncollected days — never an empty
  schedule that implies the cinema is shut.
- `?date=` survives a reload and is shareable.
- The workflow builds and deploys without a Cloudflare 401.
