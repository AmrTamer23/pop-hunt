import { useEffect, useRef } from 'react'
import { dayLabel } from '../lib/format'

/** Mirrors the date strip the cinemas themselves use. */
export function DateStrip({
  dates,
  selected,
  onSelect,
}: {
  dates: string[]
  selected: string
  onSelect: (iso: string) => void
}) {
  const selectedRef = useRef<HTMLButtonElement>(null)

  // The strip scrolls, and a deep link or a shared URL can land on a day that
  // starts off the right edge - leaving a page where nothing looks selected.
  useEffect(() => {
    // jsdom has no matchMedia; a missing one is not a preference for less
    // motion, so fall back to animating.
    const reduced =
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

    selectedRef.current?.scrollIntoView({
      // 'nearest' vertically: this must move the strip, never the page.
      block: 'nearest',
      inline: 'center',
      behavior: reduced ? 'auto' : 'smooth',
    })
  }, [selected])

  return (
    <div className="strip" role="group" aria-label="Choose a day">
      {dates.map((iso) => (
        <button
          key={iso}
          ref={iso === selected ? selectedRef : undefined}
          type="button"
          // aria-pressed, not just a class: the selection must be conveyed to
          // assistive tech, not only to sighted users.
          aria-pressed={iso === selected}
          className={
            iso === selected ? 'strip__day strip__day--selected' : 'strip__day'
          }
          onClick={() => onSelect(iso)}
        >
          {dayLabel(iso)}
        </button>
      ))}
    </div>
  )
}
