export type FixtureStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'

export interface FixtureTeam {
  id: string
  name: string
  logo?: string
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

export type LiveFixtureEventType = 'goal' | 'card' | 'substitution'

export interface LiveFixtureEvent {
  type: LiveFixtureEventType
  detail: string | null
  elapsed: number | null
  extra: number | null
  teamId: string | null
  teamName: string | null
  player: string | null
  assist: string | null
}

export interface LiveFixtureState {
  period: string
  elapsed: number | null
  extra: number | null
  events: LiveFixtureEvent[]
}

export interface Fixture {
  id: string
  competition: FixtureCompetition
  home: FixtureTeam
  away: FixtureTeam
  kickoff: string
  status: FixtureStatus
  score: FixtureScore | null
  live?: LiveFixtureState
}

export interface FixtureRange {
  from: string
  to: string
}

export interface FixtureDocument {
  schemaVersion: 1
  competition: FixtureCompetition
  generatedAt: string
  range: FixtureRange
  fixtures: Fixture[]
}

export interface LiveFixtureSnapshot {
  id: string
  competitionId: string
  period: string
  elapsed: number | null
  extra: number | null
  score: FixtureScore
  events: LiveFixtureEvent[]
}

export interface LiveFixtureDocument {
  schemaVersion: 1
  generatedAt: string
  expiresAt: string
  fixtures: LiveFixtureSnapshot[]
}
