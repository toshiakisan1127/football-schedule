export type FixtureStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'

export interface FixtureTeam {
  id: string
  name: string
}

export interface FixtureCompetition {
  id: string
  name: string
  country: string
}

export interface FixtureScore {
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
  score: FixtureScore | null
}

export interface FixtureDocument {
  schemaVersion: 1
  generatedAt: string
  range: {
    from: string
    to: string
  }
  fixtures: Fixture[]
}
