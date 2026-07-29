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
  return (
    <div className="strip" role="group" aria-label="Choose a day">
      {dates.map((iso) => (
        <button
          key={iso}
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
