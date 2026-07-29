import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DateStrip } from './DateStrip'

const dates = ['2026-07-30', '2026-07-31', '2026-08-01']

// jsdom implements neither scrollIntoView nor matchMedia.
const scrollIntoView = vi.fn()
HTMLElement.prototype.scrollIntoView = scrollIntoView

beforeEach(() => {
  scrollIntoView.mockClear()
})

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

  // A deep link can select a day that sits off the right edge of a strip that
  // scrolls. Without this the page reads as though nothing is selected.
  it('scrolls the selected day into view on mount', () => {
    render(<DateStrip dates={dates} selected="2026-08-01" onSelect={() => {}} />)
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(scrollIntoView.mock.contexts[0]).toBe(
      screen.getByRole('button', { name: /1 Aug/ }),
    )
  })

  it('scrolls again when the selected day changes', () => {
    const { rerender } = render(
      <DateStrip dates={dates} selected="2026-07-30" onSelect={() => {}} />,
    )
    scrollIntoView.mockClear()

    rerender(<DateStrip dates={dates} selected="2026-08-01" onSelect={() => {}} />)

    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(scrollIntoView.mock.contexts[0]).toBe(
      screen.getByRole('button', { name: /1 Aug/ }),
    )
  })

  // block: 'nearest' is what keeps this to the strip - anything else scrolls
  // the whole page to the date row.
  it('scrolls the strip, not the page', () => {
    render(<DateStrip dates={dates} selected="2026-07-31" onSelect={() => {}} />)
    expect(scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: 'nearest' }),
    )
  })
})
