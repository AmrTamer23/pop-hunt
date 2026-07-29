import { Link, createFileRoute } from '@tanstack/react-router'
import { EventFeed } from '../components/EventFeed'
import { TargetCard } from '../components/TargetCard'
import { loadDashboard } from '../lib/data'

export const Route = createFileRoute('/')({
  loader: () => loadDashboard(),
  component: Overview,
})

function Overview() {
  const { snapshot, events } = Route.useLoaderData()
  return (
    <>
      <section className="section">
        <h2 className="section__title">Recent openings</h2>
        <EventFeed events={events} />
      </section>
      <section className="section">
        <h2 className="section__title">Tracked cinemas</h2>
        <div className="grid">
          {snapshot.targets.map((target) => (
            <TargetCard key={target.id} target={target}>
              <Link to="/targets/$targetId" params={{ targetId: target.id }} className="button">
                View showtimes
              </Link>
            </TargetCard>
          ))}
        </div>
      </section>
    </>
  )
}
