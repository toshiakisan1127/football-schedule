import type {
  FixtureDocument,
  FixtureCompetition,
  LegacyFixtureDocument,
} from '../types/fixture'

const FIXTURE_SOURCES = [
  { id: 'epl', file: 'premier-league.json' },
  { id: 'laliga', file: 'laliga.json' },
  { id: 'bundesliga', file: 'bundesliga.json' },
] as const

const sortDocuments = (documents: FixtureDocument[]) =>
  [...documents].sort((a, b) => a.competition.id.localeCompare(b.competition.id))

const documentsFromLegacy = (legacy: LegacyFixtureDocument): FixtureDocument[] => {
  const fixturesByCompetition = new Map<string, LegacyFixtureDocument['fixtures']>()
  const competitionById = new Map<string, FixtureCompetition>()

  for (const fixture of legacy.fixtures) {
    competitionById.set(fixture.competition.id, fixture.competition)
    const fixtures = fixturesByCompetition.get(fixture.competition.id) ?? []
    fixtures.push(fixture)
    fixturesByCompetition.set(fixture.competition.id, fixtures)
  }

  return sortDocuments(
    [...fixturesByCompetition.entries()].flatMap(([competitionId, fixtures]) => {
      const competition = competitionById.get(competitionId)
      if (!competition) return []

      return [{
        schemaVersion: legacy.schemaVersion,
        competition,
        generatedAt: legacy.generatedAt,
        range: legacy.range,
        fixtures,
      }]
    }),
  )
}

export const useFixtureDocuments = async (baseURL: string) => {
  const splitUrls = FIXTURE_SOURCES.map(
    (source) => `${baseURL}data/fixtures/${source.file}`,
  )
  const legacyUrl = `${baseURL}data/fixtures.json`

  const {
    data: documents,
    status,
    error,
  } = await useAsyncData<FixtureDocument[]>(
    'fixture-documents',
    async () => {
      try {
        const loaded = await Promise.all(
          splitUrls.map((url) => $fetch<FixtureDocument>(url, { cache: 'no-store' })),
        )
        return sortDocuments(loaded)
      } catch {
        const legacy = await $fetch<LegacyFixtureDocument>(legacyUrl, { cache: 'no-store' })
        return documentsFromLegacy(legacy)
      }
    },
    { server: false },
  )

  const data = computed<LegacyFixtureDocument | null>(() => {
    const currentDocuments = documents.value ?? []
    if (currentDocuments.length === 0) return null

    const generatedAt = currentDocuments
      .map((document) => document.generatedAt)
      .sort()[0]
    if (!generatedAt) return null

    const from = currentDocuments
      .map((document) => document.range.from)
      .sort()[0]
    const to = currentDocuments
      .map((document) => document.range.to)
      .sort()
      .at(-1)
    if (!from || !to) return null

    const fixtures = currentDocuments
      .flatMap((document) => document.fixtures)
      .sort((a, b) =>
        a.kickoff.localeCompare(b.kickoff) || a.id.localeCompare(b.id),
      )

    return {
      schemaVersion: 1,
      generatedAt,
      range: { from, to },
      fixtures,
    }
  })

  return { documents, data, status, error }
}
