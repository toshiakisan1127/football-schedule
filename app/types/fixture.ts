export type FixtureStatus = 'scheduled' | 'postponed' | 'cancelled'

export interface FixtureTeam {
  id: string
  name: string
}

export interface FixtureCompetition {
  id: string
  name: string
  country: string
}

export interface Fixture {
  id: string
  competition: FixtureCompetition
  home: FixtureTeam
  away: FixtureTeam
  kickoff: string
  status: FixtureStatus
}

export interface FixtureDocument {
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
