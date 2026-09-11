import type { FixtureDocument } from '../types/fixture'

const FIXTURE_SOURCES = [
  { id: 'epl', file: 'premier-league.json' },
  { id: 'laliga', file: 'laliga.json' },
  { id: 'bundesliga', file: 'bundesliga.json' },
  { id: 'ligue1', file: 'ligue1.json' },
  { id: 'seriea', file: 'serie-a.json' },
] as const

const sortDocuments = (documents: FixtureDocument[]) =>
  [...documents].sort((a, b) => a.competition.id.localeCompare(b.competition.id))

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

          return value
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

  const data = computed(() => {
    const currentDocuments = documents.value ?? []
    if (currentDocuments.length === 0) return null

    const fixtures = currentDocuments
      .flatMap((document) => document.fixtures)
      .sort((a, b) =>
        a.kickoff.localeCompare(b.kickoff) || a.id.localeCompare(b.id),
      )

    return { fixtures }
  })

  return { documents, data, status, error }
}
