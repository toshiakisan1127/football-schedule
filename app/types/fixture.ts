export type FixtureStatus = 'scheduled' | 'finished' | 'postponed' | 'cancelled'

export interface FixtureTeam {
  id: string
  name: string
}

export interface FixtureCompetition {
  id: string
  name: string
  country: string
}

export interface FixtureResult {
  home: number
  away: number
}

export interface Fixture {
  id: string
  competition: FixtureCompetition
  home: FixtureTeam
  away: FixtureTeam
  kickoff: string
  status: FixtureStatus
  result: FixtureResult | null
}

export interface FixtureDocument {
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
