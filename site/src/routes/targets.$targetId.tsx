import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { DateStrip } from '../components/DateStrip'
import { MovieCard } from '../components/MovieCard'
import { StatusBadge } from '../components/StatusBadge'
import { loadDashboard } from '../lib/data'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export const Route = createFileRoute('/targets/$targetId')({
  validateSearch: (search: Record<string, unknown>): { date?: string } => {
    const date = search.date
    return typeof date === 'string' && ISO_DATE.test(date) ? { date } : {}
  },
  loader: () => loadDashboard(),
  component: TargetDetail,
})

function TargetDetail() {
  const { targetId } = Route.useParams()
  const { date } = Route.useSearch()
  const { snapshot } = Route.useLoaderData()
  const navigate = useNavigate({ from: Route.fullPath })

  const target = snapshot.targets.find((t) => t.id === targetId)
  if (!target) {
    return (
      <p className="empty">
        No such target. <Link to="/">Back to overview</Link>
      </p>
    )
  }

  // Default to the first bookable day; the param makes a day linkable.
  const selected = date && target.dates.includes(date) ? date : target.dates[0]

  return (
    <section className="section">
      <header className="detail__header">
        <h2 className="section__title">{target.label}</h2>
        <StatusBadge status={target.status} staleSince={target.stale_since} />
      </header>

      {target.dates.length === 0 ? (
        <p className="empty">No bookable dates were found for this target.</p>
      ) : (
        <>
          <DateStrip
            dates={target.dates}
            selected={selected}
            onSelect={(next) =>
              navigate({ search: { date: next }, replace: true })
            }
          />
          <div className="grid">
            {target.movies.map((movie) => (
              <MovieCard key={movie.title} movie={movie} date={selected} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
