import { beforeEach, describe, expect, it, vi } from 'vitest'
import { __resetDashboardCache, loadDashboard } from './data'
import snapshotFixture from '../__fixtures__/snapshot.json'

function mockFetch(handlers: Record<string, () => Response>) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const key = Object.keys(handlers).find((k) => url.includes(k))
    return Promise.resolve(key ? handlers[key]() : new Response('', { status: 404 }))
  })
}

const okSnapshot = () => new Response(JSON.stringify(snapshotFixture), { status: 200 })
const okEvents = () =>
  new Response(
    JSON.stringify([
      { at: 't1', target_id: 'a', label: 'A', previous: null, new_max: '2026-08-06', added: ['2026-08-06'], url: 'u' },
    ]),
    { status: 200 },
  )

describe('loadDashboard', () => {
  beforeEach(() => __resetDashboardCache())

  it('loads the snapshot and events together', async () => {
    vi.stubGlobal('fetch', mockFetch({ 'snapshot.json': okSnapshot, 'events.json': okEvents }))
    const { snapshot, events } = await loadDashboard()
    expect(snapshot.targets.length).toBeGreaterThan(0)
    expect(events).toHaveLength(1)
  })

  it('treats a missing events file as an empty feed', async () => {
    // events.json does not exist until the first booking day opens -> 404.
    vi.stubGlobal('fetch', mockFetch({ 'snapshot.json': okSnapshot }))
    const { events } = await loadDashboard()
    expect(events).toEqual([])
  })

  it('yields an empty dashboard rather than throwing when the snapshot is missing', async () => {
    vi.stubGlobal('fetch', mockFetch({}))
    const { snapshot, events } = await loadDashboard()
    expect(snapshot.targets).toEqual([])
    expect(snapshot.generated_at).toBeNull()
    expect(events).toEqual([])
  })

  it('fetches only once across repeated calls', async () => {
    const fetchMock = mockFetch({ 'snapshot.json': okSnapshot, 'events.json': okEvents })
    vi.stubGlobal('fetch', fetchMock)
    await loadDashboard()
    await loadDashboard()
    expect(fetchMock).toHaveBeenCalledTimes(2) // snapshot + events, not four
  })
})
