import { formatGeneratedAt } from '../lib/format'
import type { TargetStatus } from '../types'

/** Silent when healthy - a badge on every card would be noise. */
export function StatusBadge({
  status,
  staleSince,
}: {
  status: TargetStatus
  staleSince?: string
}) {
  if (status === 'ok') return null
  if (status === 'error') {
    return <span className="badge badge--error">Unavailable</span>
  }
  return (
    <span className="badge badge--stale">
      Stale since {formatGeneratedAt(staleSince ?? null)}
    </span>
  )
}
