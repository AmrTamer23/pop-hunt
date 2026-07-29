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
