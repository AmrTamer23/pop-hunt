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
