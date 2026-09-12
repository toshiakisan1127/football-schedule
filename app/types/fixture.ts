export type FixtureStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'
export type LiveFixtureEventType = 'goal' | 'card' | 'substitution' | 'other'

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

export interface LiveFixtureEvent {
  elapsed: number
  extra: number | null
  teamId: string | null
  player: string | null
  assist: string | null
  type: LiveFixtureEventType
  detail: string | null
  comments: string | null
}

export interface LiveFixtureSnapshot {
  statusShort: string
  elapsed: number
  extra: number | null
  score: FixtureScore
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
  live?: LiveFixtureSnapshot
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

export interface LiveFixtureRecord extends LiveFixtureSnapshot {
  id: string
  competitionId: string
}

export interface LiveFixtureDocument {
  schemaVersion: 1
  generatedAt: string
  fixtures: LiveFixtureRecord[]
}
