import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders nothing when the target is healthy', () => {
    const { container } = render(<StatusBadge status="ok" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('explains stale data and when it went stale', () => {
    const staleSince = '2026-07-29T04:30:36+03:00'
    // Derived from the same instant rather than a hardcoded wall clock, matching
    // the convention in lib/format.test.ts. The suite pins TZ=America/New_York,
    // where this +03:00 timestamp is 28 Jul - asserting "29 Jul" would encode
    // the author's timezone rather than the contract.
    const stamp = new Date(staleSince).toLocaleString('en-GB', {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    })
    render(<StatusBadge status="stale" staleSince={staleSince} />)
    expect(screen.getByText(/stale/i)).toBeInTheDocument()
    expect(screen.getByText(new RegExp(stamp))).toBeInTheDocument()
  })

  it('flags an error state', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument()
  })
})
