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
