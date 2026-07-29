import type { ReactNode } from 'react'
import { bookingWindowLabel } from '../lib/format'
import type { TargetEntry } from '../types'
import { StatusBadge } from './StatusBadge'

/**
 * Router-free by design: the internal detail link arrives as `children` so this
 * stays a pure component that renders without a router in tests.
 */
export function TargetCard({
  target,
  children,
}: {
  target: TargetEntry
  children?: ReactNode
}) {
  return (
    <article className="card">
      <header className="card__header">
        <h3 className="card__title">{target.label}</h3>
        <StatusBadge status={target.status} staleSince={target.stale_since} />
      </header>
      <p className="card__window">{bookingWindowLabel(target)}</p>
      <footer className="card__actions">
        {children}
        <a
          className="button button--ghost"
          href={target.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Book at cinema
        </a>
      </footer>
    </article>
  )
}
