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
