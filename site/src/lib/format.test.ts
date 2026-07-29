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
