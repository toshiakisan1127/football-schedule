import type {
  FixtureDocument,
  LiveFixtureDocument,
  LiveFixtureEvent,
  LiveFixtureRecord,
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

const LIVE_DOCUMENT_MAX_AGE_MS = 15 * 60 * 1000

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

const isLiveFixtureEvent = (value: unknown): value is LiveFixtureEvent => {
  if (!isRecord(value)) return false
  if (typeof value.elapsed !== 'number') return false
  if (value.extra !== null && typeof value.extra !== 'number') return false
  if (value.teamId !== null && typeof value.teamId !== 'string') return false
  if (value.player !== null && typeof value.player !== 'string') return false
  if (value.assist !== null && typeof value.assist !== 'string') return false
  if (!['goal', 'card', 'substitution', 'other'].includes(String(value.type))) return false
  if (value.detail !== null && typeof value.detail !== 'string') return false
  if (value.comments !== null && typeof value.comments !== 'string') return false
  return true
}

const isLiveFixtureRecord = (value: unknown): value is LiveFixtureRecord => {
  if (!isRecord(value)) return false
  if (typeof value.id !== 'string') return false
  if (typeof value.competitionId !== 'string') return false
  if (typeof value.statusShort !== 'string') return false
  if (typeof value.elapsed !== 'number') return false
  if (value.extra !== null && typeof value.extra !== 'number') return false
  if (!isRecord(value.score)) return false
  if (typeof value.score.home !== 'number' || typeof value.score.away !== 'number') return false
  if (!Array.isArray(value.events) || !value.events.every(isLiveFixtureEvent)) return false
  return true
}

const isLiveFixtureDocument = (value: unknown): value is LiveFixtureDocument => {
  if (!isRecord(value)) return false
  if (value.schemaVersion !== 1) return false
  if (typeof value.generatedAt !== 'string') return false
  if (!Array.isArray(value.fixtures) || !value.fixtures.every(isLiveFixtureRecord)) return false

  const generatedAt = new Date(value.generatedAt).getTime()
  if (!Number.isFinite(generatedAt)) return false
  return Date.now() - generatedAt <= LIVE_DOCUMENT_MAX_AGE_MS
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
    refresh: refreshLive,
  } = await useAsyncData<LiveFixtureDocument | null>(
    'live-fixtures',
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
    { server: false, default: () => null },
  )

  const data = computed(() => {
    const currentDocuments = documents.value ?? []
    if (currentDocuments.length === 0) return null

    const liveByFixture = new Map(
      (liveDocument.value?.fixtures ?? []).map((fixture) => [
        `${fixture.competitionId}:${fixture.id}`,
        fixture,
      ]),
    )

    const fixtures = currentDocuments
      .flatMap((document) => document.fixtures)
      .map((fixture) => {
        const live = liveByFixture.get(`${fixture.competition.id}:${fixture.id}`)
        if (!live) return fixture

        return {
          ...fixture,
          status: 'live' as const,
          score: live.score,
          live: {
            statusShort: live.statusShort,
            elapsed: live.elapsed,
            extra: live.extra,
            score: live.score,
            events: live.events,
          },
        }
      })
      .sort((a, b) =>
        a.kickoff.localeCompare(b.kickoff) || a.id.localeCompare(b.id),
      )

    return { fixtures }
  })

  return { documents, data, status, error, refreshLive }
}
