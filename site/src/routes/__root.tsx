import { Link, Outlet, createRootRoute } from '@tanstack/react-router'
import { loadDashboard } from '../lib/data'
import { formatGeneratedAt } from '../lib/format'

export const Route = createRootRoute({
  loader: () => loadDashboard(),
  component: RootLayout,
})

function RootLayout() {
  const { snapshot } = Route.useLoaderData()
  return (
    <div className="app">
      <header className="app__header">
        <Link to="/" className="app__brand">
          pop&#8209;hunt
        </Link>
        {/* Two different timestamps, deliberately. "Last checked" proves the
            monitor ran; "data as of" is when anything last changed. On a quiet
            day they differ by hours, and showing only the latter looks broken. */}
        <p className="app__meta">
          <span>Last checked {formatGeneratedAt(__BUILT_AT__)}</span>
          <span>Data as of {formatGeneratedAt(snapshot.generated_at)}</span>
        </p>
      </header>
      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
