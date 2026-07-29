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
