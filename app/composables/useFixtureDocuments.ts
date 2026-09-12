import type {
  Fixture,
  FixtureDocument,
  LiveFixtureDocument,
  LiveFixtureEvent,
  LiveFixtureSnapshot,
} from '../types/fixture'

const FIXTURE_SOURCES = [
  { id: 'epl', file: 'premier-league.json' },
  { id: 'laliga', file: 'laliga.json' },
  { id: 'bundesliga', file: 'bundesliga.json' },
  { id: 'ligue1', file: 'ligue1.json' },
  { id: 'j1', file: 'j1.json' },
  { id: 'ucl', file: 'champions-league.json' },
  { id: 'uel', file: 'europa-league.json' },
  { id: 'uecl', file: 'conference-league.json' },
] as const

const LIVE_REFRESH_INTERVAL_MS = 60_000
const LIVE_STALE_AFTER_MS = 15 * 60_000

const sortDocuments = (documents: FixtureDocument[]) =>
  [...documents].sort((a, b) => a.competition.id.localeCompare(b.competition.id))

const hideLiveStatus = (document: FixtureDocument): FixtureDocument => ({
  ...document,
  fixtures: document.fixtures.map((fixture) =>
    fixture.status === 'live'
      ? { ...fixture, status: 'scheduled' }
      : fixture,
  ),
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isFixtureDocument = (
  value: unknown,
  expectedCompetitionId: string,
): value is FixtureDocument => {
  if (!isRecord(value)) return false
  if (value.schemaVersion !== 1) return false
  if (!isRecord(value.competition)) return false
  if (value.competition.id !== expectedCompetitionId) return false
  if (typeof value.competition.name !== 'string') return false
  if (typeof value.competition.country !== 'string') return false
  if (typeof value.generatedAt !== 'string') return false
  if (!isRecord(value.range)) return false
  if (typeof value.range.from !== 'string' || typeof value.range.to !== 'string') return false
  return Array.isArray(value.fixtures)
}

const isNullableNumber = (value: unknown): value is number | null =>
  value === null || typeof value === 'number'

const isNullableString = (value: unknown): value is string | null =>
  value === null || typeof value === 'string'

const isLiveEvent = (value: unknown): value is LiveFixtureEvent => {
  if (!isRecord(value)) return false
  if (!['goal', 'card', 'substitution'].includes(String(value.type))) return false
  if (!isNullableString(value.detail)) return false
  if (!isNullableNumber(value.elapsed) || !isNullableNumber(value.extra)) return false
  if (!isNullableString(value.teamId) || !isNullableString(value.teamName)) return false
  if (!isNullableString(value.player) || !isNullableString(value.assist)) return false
  return true
}

const isLiveFixture = (value: unknown): value is LiveFixtureSnapshot => {
  if (!isRecord(value)) return false
  if (typeof value.id !== 'string' || typeof value.competitionId !== 'string') return false
  if (typeof value.period !== 'string') return false
  if (!isNullableNumber(value.elapsed) || !isNullableNumber(value.extra)) return false
  if (!isRecord(value.score)) return false
  if (typeof value.score.home !== 'number' || typeof value.score.away !== 'number') return false
  return Array.isArray(value.events) && value.events.every(isLiveEvent)
}

const isLiveFixtureDocument = (value: unknown): value is LiveFixtureDocument => {
  if (!isRecord(value)) return false
  if (value.schemaVersion !== 1 || typeof value.generatedAt !== 'string') return false
  return Array.isArray(value.fixtures) && value.fixtures.every(isLiveFixture)
}

const isFreshLiveDocument = (document: LiveFixtureDocument | null) => {
  if (!document) return false
  const generatedAt = new Date(document.generatedAt).getTime()
  return Number.isFinite(generatedAt) && Date.now() - generatedAt <= LIVE_STALE_AFTER_MS
}

const mergeLiveFixture = (
  fixture: Fixture,
  liveFixtures: Map<string, LiveFixtureSnapshot>,
): Fixture => {
  const live = liveFixtures.get(fixture.id)
  if (!live || live.competitionId !== fixture.competition.id) return fixture

  return {
    ...fixture,
    status: 'live',
    score: live.score,
    live: {
      period: live.period,
      elapsed: live.elapsed,
      extra: live.extra,
      events: live.events,
    },
  }
}

export const useFixtureDocuments = async (baseURL: string) => {
  const {
    data: documents,
    status,
    error,
  } = await useAsyncData<FixtureDocument[]>(
    'fixture-documents',
    async () => {
      const results = await Promise.allSettled(
        FIXTURE_SOURCES.map(async (source) => {
          const url = `${baseURL}data/fixtures/${source.file}`
          const value = await $fetch<unknown>(url, { cache: 'no-store' })

          if (!isFixtureDocument(value, source.id)) {
            throw new Error(`Invalid fixture document: ${source.id}`)
          }

          return hideLiveStatus(value)
        }),
      )

      const loaded = results.flatMap((result) =>
        result.status === 'fulfilled' ? [result.value] : [],
      )

      if (loaded.length === 0) {
        throw new Error('Failed to load all fixture documents')
      }

      return sortDocuments(loaded)
    },
    { server: false },
  )

  const {
    data: liveDocument,
    refresh: refreshLiveDocument,
  } = await useAsyncData<LiveFixtureDocument | null>(
    'live-fixture-document',
    async () => {
      try {
        const value = await $fetch<unknown>(`${baseURL}data/fixtures/live.json`, {
          cache: 'no-store',
        })
        return isLiveFixtureDocument(value) ? value : null
      } catch {
        return null
      }
    },
    { server: false },
  )

  let liveRefreshTimer: ReturnType<typeof setInterval> | undefined
  onMounted(() => {
    liveRefreshTimer = setInterval(() => {
      void refreshLiveDocument()
    }, LIVE_REFRESH_INTERVAL_MS)
  })
  onUnmounted(() => {
    if (liveRefreshTimer) clearInterval(liveRefreshTimer)
  })

  const data = computed(() => {
    const currentDocuments = documents.value ?? []
    if (currentDocuments.length === 0) return null

    const liveFixtures = isFreshLiveDocument(liveDocument.value)
      ? new Map(liveDocument.value?.fixtures.map((fixture) => [fixture.id, fixture]) ?? [])
      : new Map<string, LiveFixtureSnapshot>()

    const fixtures = currentDocuments
      .flatMap((document) => document.fixtures)
      .map((fixture) => mergeLiveFixture(fixture, liveFixtures))
      .sort((a, b) =>
        a.kickoff.localeCompare(b.kickoff) || a.id.localeCompare(b.id),
      )

    return { fixtures }
  })

  return { documents, data, status, error }
}
