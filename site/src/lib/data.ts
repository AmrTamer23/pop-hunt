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
