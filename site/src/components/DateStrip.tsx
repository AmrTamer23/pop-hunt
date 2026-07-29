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
  const firstRun = useRef(true)

  // The strip scrolls, and a deep link or a shared URL can land on a day that
  // starts off the right edge - leaving a page where nothing looks selected.
  useEffect(() => {
    // jsdom has no matchMedia; a missing one is not a preference for less
    // motion, so fall back to animating.
    const reduced =
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

    // Instant on first render, animated afterwards. A background tab - opened
    // with cmd-click, or restored with the session - throttles the frames a
    // smooth scroll needs, so it would never arrive: the reader switches to
    // the tab and finds the strip still at the left, with nothing left to
    // re-trigger it. First render just has to BE in the right place. The
    // animation is worth it only later, where it shows movement the reader
    // asked for by picking a day.
    const behavior = firstRun.current || reduced ? 'auto' : 'smooth'
    firstRun.current = false

    selectedRef.current?.scrollIntoView({
      // 'nearest' vertically: this must move the strip, never the page.
      block: 'nearest',
      inline: 'center',
      behavior,
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
