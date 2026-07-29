import { dayLabel, formatGeneratedAt } from '../lib/format'
import type { OpeningEvent } from '../types'

/** `events.json` is already stored newest-first - do not re-sort it. */
export function EventFeed({ events }: { events: OpeningEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="empty">
        No openings recorded yet. When a cinema opens a new bookable day it will
        appear here, and you will get a Telegram alert.
      </p>
    )
  }

  return (
    <ol className="feed">
      {events.map((event) => (
        <li key={`${event.target_id}-${event.at}`} className="feed__item">
          <p className="feed__label">{event.label}</p>
          <p className="feed__dates">
            Opened{' '}
            {event.added.map((iso, index) => (
              <span key={iso}>
                {index > 0 && ', '}
                <strong>{dayLabel(iso)}</strong>
              </span>
            ))}
          </p>
          <p className="feed__meta">{formatGeneratedAt(event.at)}</p>
        </li>
      ))}
    </ol>
  )
}
