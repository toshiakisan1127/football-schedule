import type { FixtureDocument } from '../types/fixture'

const FIXTURE_SOURCES = [
  { id: 'epl', file: 'premier-league.json' },
  { id: 'laliga', file: 'laliga.json' },
  { id: 'bundesliga', file: 'bundesliga.json' },
] as const

const sortDocuments = (documents: FixtureDocument[]) =>
  [...documents].sort((a, b) => a.competition.id.localeCompare(b.competition.id))

export const useFixtureDocuments = async (baseURL: string) => {
  const splitUrls = FIXTURE_SOURCES.map(
    (source) => `${baseURL}data/fixtures/${source.file}`,
  )

  const {
    data: documents,
    status,
    error,
  } = await useAsyncData<FixtureDocument[]>(
    'fixture-documents',
    async () => sortDocuments(
      await Promise.all(
        splitUrls.map((url) => $fetch<FixtureDocument>(url, { cache: 'no-store' })),
      ),
    ),
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
