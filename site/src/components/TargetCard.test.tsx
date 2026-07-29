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
