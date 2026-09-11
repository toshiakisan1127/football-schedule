<script setup lang="ts">
import type { Fixture, FixtureDocument } from './types/fixture'

type DateFilter = 'all' | 'today' | 'tomorrow' | 'weekend'
type Theme = 'light' | 'dark'

type TeamFilter = {
  id: string
  name: string
  competitions: string[]
}

const FIXTURE_TIME_ZONE = 'Asia/Tokyo'

const runtimeConfig = useRuntimeConfig()
const baseURL = runtimeConfig.app.baseURL.endsWith('/')
  ? runtimeConfig.app.baseURL
  : `${runtimeConfig.app.baseURL}/`

const fixturesUrl = `${baseURL}data/fixtures.json`

const { data, status, error } = await useFetch<FixtureDocument>(fixturesUrl, {
  server: false,
  cache: 'no-store',
})

const selectedFilter = ref<DateFilter>('all')
const selectedCompetitions = ref<Set<string>>(new Set())
const draftCompetitions = ref<Set<string>>(new Set())
const selectedTeams = ref<Set<string>>(new Set())
const draftTeams = ref<Set<string>>(new Set())
const teamSearch = ref('')
const isLeagueSettingsOpen = ref(false)
const isTeamSettingsOpen = ref(false)
const currentDate = ref<Date | null>(null)
const theme = ref<Theme>('dark')
const showResults = ref(false)

const dateFilters: { value: DateFilter; label: string }[] = [
  { value: 'all', label: '全日程' },
  { value: 'today', label: '今日' },
  { value: 'tomorrow', label: '明日' },
  { value: 'weekend', label: '今週末' },
]

const competitionFilters = computed(() => {
  const competitions = new Map<string, { id: string; name: string; country: string }>()

  for (const fixture of data.value?.fixtures ?? []) {
    if (!competitions.has(fixture.competition.id)) {
      competitions.set(fixture.competition.id, fixture.competition)
    }
  }

  return [...competitions.values()].sort((a, b) =>
    `${a.country}-${a.name}`.localeCompare(`${b.country}-${b.name}`),
  )
})

const teamFilters = computed<TeamFilter[]>(() => {
  const teams = new Map<string, { id: string; name: string; competitions: Set<string> }>()

  for (const fixture of data.value?.fixtures ?? []) {
    for (const team of [fixture.home, fixture.away]) {
      const current = teams.get(team.id) ?? {
        id: team.id,
        name: team.name,
        competitions: new Set<string>(),
      }

      current.competitions.add(fixture.competition.name)
      teams.set(team.id, current)
    }
  }

  return [...teams.values()]
    .map((team) => ({
      id: team.id,
      name: team.name,
      competitions: [...team.competitions].sort((a, b) => a.localeCompare(b)),
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
})

const filteredTeamOptions = computed(() => {
  const query = teamSearch.value.trim().toLocaleLowerCase()
  if (!query) return teamFilters.value

  return teamFilters.value.filter((team) =>
    team.name.toLocaleLowerCase().includes(query)
    || team.competitions.some((competition) => competition.toLocaleLowerCase().includes(query)),
  )
})

const isAllCompetitionsSelected = computed(() => selectedCompetitions.value.size === 0)
const isAllDraftCompetitionsSelected = computed(() => draftCompetitions.value.size === 0)
const isAllTeamsSelected = computed(() => selectedTeams.value.size === 0)
const isAllDraftTeamsSelected = computed(() => draftTeams.value.size === 0)

const selectedCompetitionList = computed(() => {
  if (isAllCompetitionsSelected.value) return []
  return competitionFilters.value.filter((competition) => selectedCompetitions.value.has(competition.id))
})

const selectedTeamList = computed(() => {
  if (isAllTeamsSelected.value) return []
  return teamFilters.value.filter((team) => selectedTeams.value.has(team.id))
})

const persistCompetitionSelection = () => {
  localStorage.setItem(
    'football-schedule-competitions',
    JSON.stringify([...selectedCompetitions.value]),
  )
}

const persistTeamSelection = () => {
  localStorage.setItem(
    'football-schedule-teams',
    JSON.stringify([...selectedTeams.value]),
  )
}

const openLeagueSettings = () => {
  draftCompetitions.value = new Set(selectedCompetitions.value)
  isLeagueSettingsOpen.value = true
}

const closeLeagueSettings = () => {
  isLeagueSettingsOpen.value = false
}

const selectAllDraftCompetitions = () => {
  draftCompetitions.value = new Set()
}

const toggleDraftCompetition = (competitionId: string) => {
  const next = new Set(draftCompetitions.value)

  if (next.size === 0) {
    next.add(competitionId)
  } else if (next.has(competitionId)) {
    next.delete(competitionId)
  } else {
    next.add(competitionId)
  }

  draftCompetitions.value = next.size === 0 ? new Set() : next
}

const saveLeagueSettings = () => {
  selectedCompetitions.value = new Set(draftCompetitions.value)
  persistCompetitionSelection()
  closeLeagueSettings()
}

const openTeamSettings = () => {
  draftTeams.value = new Set(selectedTeams.value)
  teamSearch.value = ''
  isTeamSettingsOpen.value = true
}

const closeTeamSettings = () => {
  isTeamSettingsOpen.value = false
  teamSearch.value = ''
}

const selectAllDraftTeams = () => {
  draftTeams.value = new Set()
}

const toggleDraftTeam = (teamId: string) => {
  const next = new Set(draftTeams.value)

  if (next.size === 0) {
    next.add(teamId)
  } else if (next.has(teamId)) {
    next.delete(teamId)
  } else {
    next.add(teamId)
  }

  draftTeams.value = next.size === 0 ? new Set() : next
}

const saveTeamSettings = () => {
  selectedTeams.value = new Set(draftTeams.value)
  persistTeamSelection()
  closeTeamSettings()
}

const localDateKeyFromDate = (date: Date) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: FIXTURE_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)

  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

const localDateKey = (iso: string) => localDateKeyFromDate(new Date(iso))

const addDaysToDateKey = (dateKey: string, days: number) => {
  const [year = 0, month = 1, day = 1] = dateKey.split('-').map(Number)
  const next = new Date(Date.UTC(year, month - 1, day + days))
  return next.toISOString().slice(0, 10)
}

const dayOfWeekFromDateKey = (dateKey: string) => {
  const [year = 0, month = 1, day = 1] = dateKey.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day)).getUTCDay()
}

const targetDateKeys = computed(() => {
  if (selectedFilter.value === 'all') return null
  if (!currentDate.value) return new Set<string>()

  const todayKey = localDateKeyFromDate(currentDate.value)

  if (selectedFilter.value === 'today') {
    return new Set([todayKey])
  }

  if (selectedFilter.value === 'tomorrow') {
    return new Set([addDaysToDateKey(todayKey, 1)])
  }

  const dayOfWeek = dayOfWeekFromDateKey(todayKey)
  const saturdayOffset = dayOfWeek === 0 ? -1 : 6 - dayOfWeek
  const saturdayKey = addDaysToDateKey(todayKey, saturdayOffset)
  const sundayKey = addDaysToDateKey(saturdayKey, 1)

  return new Set([saturdayKey, sundayKey])
})

const dateLabel = (iso: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    timeZone: FIXTURE_TIME_ZONE,
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date(iso))

const timeLabel = (iso: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    timeZone: FIXTURE_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))

const statusLabel = (fixture: Fixture) => {
  if (fixture.status === 'live') return '試合中'
  if (fixture.status === 'postponed') return '延期'
  if (fixture.status === 'cancelled') return '中止'
  return null
}

const resultLabel = (fixture: Fixture) => {
  if (!showResults.value || fixture.status !== 'finished' || !fixture.score) return null
  return `${fixture.score.home}–${fixture.score.away}`
}

const filteredFixtures = computed(() => {
  let fixtures = data.value?.fixtures ?? []

  if (selectedCompetitions.value.size > 0) {
    fixtures = fixtures.filter((fixture) => selectedCompetitions.value.has(fixture.competition.id))
  }

  if (selectedTeams.value.size > 0) {
    fixtures = fixtures.filter((fixture) =>
      selectedTeams.value.has(fixture.home.id) || selectedTeams.value.has(fixture.away.id),
    )
  }

  if (!targetDateKeys.value) return fixtures

  return fixtures.filter((fixture) => targetDateKeys.value?.has(localDateKey(fixture.kickoff)))
})

const groupedFixtures = computed(() => {
  const fixtures = [...filteredFixtures.value].sort(
    (a, b) => new Date(a.kickoff).getTime() - new Date(b.kickoff).getTime(),
  )

  const groups = new Map<string, Fixture[]>()
  for (const fixture of fixtures) {
    const key = localDateKey(fixture.kickoff)
    groups.set(key, [...(groups.get(key) ?? []), fixture])
  }

  return [...groups.entries()].flatMap(([key, items]) => {
    const firstFixture = items[0]
    if (!firstFixture) return []

    return [{
      key,
      label: dateLabel(firstFixture.kickoff),
      fixtures: items,
    }]
  })
})

const generatedAtLabel = computed(() => {
  if (!data.value?.generatedAt) return null

  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: FIXTURE_TIME_ZONE,
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(data.value.generatedAt))
})

const emptyMessage = computed(() => {
  const hasDisplayFilter = !isAllCompetitionsSelected.value || !isAllTeamsSelected.value
  const prefix = hasDisplayFilter ? '条件に合う' : ''

  if (selectedFilter.value === 'all') return `${prefix}表示できる試合がありません。`
  if (selectedFilter.value === 'today') return `${prefix}今日の試合はありません。`
  if (selectedFilter.value === 'tomorrow') return `${prefix}明日の試合はありません。`
  return `${prefix}今週末の試合はありません。`
})

const applyTheme = (nextTheme: Theme) => {
  theme.value = nextTheme
  document.documentElement.dataset.theme = nextTheme
}

const toggleTheme = () => {
  const nextTheme: Theme = theme.value === 'dark' ? 'light' : 'dark'
  applyTheme(nextTheme)
  localStorage.setItem('football-schedule-theme', nextTheme)
}

const toggleResults = () => {
  showResults.value = !showResults.value
  localStorage.setItem('football-schedule-show-results', String(showResults.value))
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') return

  if (isLeagueSettingsOpen.value) closeLeagueSettings()
  if (isTeamSettingsOpen.value) closeTeamSettings()
}

watch([isLeagueSettingsOpen, isTeamSettingsOpen], ([leagueOpen, teamOpen]) => {
  document.body.style.overflow = leagueOpen || teamOpen ? 'hidden' : ''
})

onMounted(() => {
  currentDate.value = new Date()

  const savedTheme = localStorage.getItem('football-schedule-theme')
  const initialTheme: Theme = savedTheme === 'light' || savedTheme === 'dark'
    ? savedTheme
    : window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'

  applyTheme(initialTheme)
  showResults.value = localStorage.getItem('football-schedule-show-results') === 'true'

  const savedCompetitions = localStorage.getItem('football-schedule-competitions')
  if (savedCompetitions) {
    try {
      const parsed = JSON.parse(savedCompetitions)
      if (Array.isArray(parsed) && parsed.every((id) => typeof id === 'string')) {
        selectedCompetitions.value = new Set(parsed)
      }
    } catch {
      localStorage.removeItem('football-schedule-competitions')
    }
  }

  const savedTeams = localStorage.getItem('football-schedule-teams')
  if (savedTeams) {
    try {
      const parsed = JSON.parse(savedTeams)
      if (Array.isArray(parsed) && parsed.every((id) => typeof id === 'string')) {
        selectedTeams.value = new Set(parsed)
      }
    } catch {
      localStorage.removeItem('football-schedule-teams')
    }
  }

  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div class="header-copy">
        <p class="eyebrow">FOOTBALL SCHEDULE</p>
        <h1>試合日程</h1>
        <p class="subtitle">日本時間で、見たいサッカーの試合時間だけ。</p>
      </div>

      <div class="header-meta">
        <div class="header-actions">
          <button
            type="button"
            class="result-toggle"
            :aria-pressed="showResults"
            @click="toggleResults"
          >
            {{ showResults ? '結果を隠す' : '結果を表示' }}
          </button>
          <button
            type="button"
            class="theme-toggle"
            :aria-label="theme === 'dark' ? 'ライトモードに切り替える' : 'ダークモードに切り替える'"
            @click="toggleTheme"
          >
            {{ theme === 'dark' ? '☀︎ ライト' : '☾ ダーク' }}
          </button>
        </div>
        <p v-if="generatedAtLabel" class="updated-at">
          更新 {{ generatedAtLabel }}
        </p>
      </div>
    </header>

    <nav class="quick-filters quick-filters--date" aria-label="日付フィルター">
      <button
        v-for="filter in dateFilters"
        :key="filter.value"
        type="button"
        class="filter-button"
        :class="{ 'filter-button--active': selectedFilter === filter.value }"
        :aria-pressed="selectedFilter === filter.value"
        @click="selectedFilter = filter.value"
      >
        {{ filter.label }}
      </button>
    </nav>

    <div class="filter-summaries">
      <section class="league-summary" aria-label="表示リーグ設定">
        <div class="league-summary__header">
          <span class="league-summary__label">表示リーグ</span>
          <button type="button" class="league-edit-button" @click="openLeagueSettings">
            編集
          </button>
        </div>

        <div class="selected-leagues">
          <span v-if="isAllCompetitionsSelected" class="league-pill">全リーグ</span>
          <span
            v-for="competition in selectedCompetitionList"
            v-else
            :key="competition.id"
            class="league-pill"
          >
            {{ competition.name }}
          </span>
        </div>
      </section>

      <section class="league-summary" aria-label="お気に入りチーム設定">
        <div class="league-summary__header">
          <span class="league-summary__label">お気に入りチーム</span>
          <button type="button" class="league-edit-button" @click="openTeamSettings">
            編集
          </button>
        </div>

        <div class="selected-leagues">
          <span v-if="isAllTeamsSelected" class="league-pill">未設定（全チーム表示）</span>
          <span
            v-for="team in selectedTeamList"
            v-else
            :key="team.id"
            class="league-pill"
          >
            {{ team.name }}
          </span>
        </div>
      </section>
    </div>

    <p v-if="status === 'pending'" class="state-message">日程を読み込んでいます…</p>
    <p v-else-if="error" class="state-message state-message--error">
      日程を読み込めませんでした。
    </p>

    <section v-else class="schedule-list">
      <article v-for="group in groupedFixtures" :key="group.key" class="day-group">
        <h2>{{ group.label }}</h2>

        <div class="fixture-list">
          <div v-for="fixture in group.fixtures" :key="fixture.id" class="fixture-row">
            <time :datetime="fixture.kickoff" class="kickoff">
              {{ timeLabel(fixture.kickoff) }}
            </time>

            <div class="fixture-main">
              <p class="competition">
                {{ fixture.competition.country }} · {{ fixture.competition.name }}
              </p>
              <p class="matchup">
                <span>{{ fixture.home.name }}</span>
                <span class="versus">vs</span>
                <span>{{ fixture.away.name }}</span>
              </p>
            </div>

            <div class="fixture-side">
              <span v-if="resultLabel(fixture)" class="fixture-result">
                {{ resultLabel(fixture) }}
              </span>
              <span
                v-else-if="statusLabel(fixture)"
                class="fixture-status"
                :class="{ 'fixture-status--live': fixture.status === 'live' }"
              >
                {{ statusLabel(fixture) }}
              </span>
            </div>
          </div>
        </div>
      </article>

      <p v-if="groupedFixtures.length === 0" class="state-message">
        {{ emptyMessage }}
      </p>
    </section>

    <Teleport to="body">
      <div
        v-if="isLeagueSettingsOpen"
        class="modal-backdrop"
        @click.self="closeLeagueSettings"
      >
        <section
          class="league-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="league-modal-title"
        >
          <header class="league-modal__header">
            <div>
              <p class="league-modal__eyebrow">表示設定</p>
              <h2 id="league-modal-title">表示するリーグ</h2>
            </div>
            <button
              type="button"
              class="modal-close-button"
              aria-label="閉じる"
              @click="closeLeagueSettings"
            >
              ×
            </button>
          </header>

          <div class="league-options">
            <button
              type="button"
              class="league-option"
              :class="{ 'league-option--selected': isAllDraftCompetitionsSelected }"
              :aria-pressed="isAllDraftCompetitionsSelected"
              @click="selectAllDraftCompetitions"
            >
              <span>
                <strong>全リーグ</strong>
                <small>すべての日程を表示</small>
              </span>
              <span class="league-option__check" aria-hidden="true">
                {{ isAllDraftCompetitionsSelected ? '✓' : '' }}
              </span>
            </button>

            <button
              v-for="competition in competitionFilters"
              :key="competition.id"
              type="button"
              class="league-option"
              :class="{ 'league-option--selected': draftCompetitions.has(competition.id) }"
              :aria-pressed="draftCompetitions.has(competition.id)"
              @click="toggleDraftCompetition(competition.id)"
            >
              <span>
                <strong>{{ competition.name }}</strong>
                <small>{{ competition.country }}</small>
              </span>
              <span class="league-option__check" aria-hidden="true">
                {{ draftCompetitions.has(competition.id) ? '✓' : '' }}
              </span>
            </button>
          </div>

          <footer class="league-modal__footer">
            <button type="button" class="modal-secondary-button" @click="closeLeagueSettings">
              キャンセル
            </button>
            <button type="button" class="modal-primary-button" @click="saveLeagueSettings">
              完了
            </button>
          </footer>
        </section>
      </div>

      <div
        v-if="isTeamSettingsOpen"
        class="modal-backdrop"
        @click.self="closeTeamSettings"
      >
        <section
          class="league-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="team-modal-title"
        >
          <header class="league-modal__header">
            <div>
              <p class="league-modal__eyebrow">表示設定</p>
              <h2 id="team-modal-title">お気に入りチーム</h2>
            </div>
            <button
              type="button"
              class="modal-close-button"
              aria-label="閉じる"
              @click="closeTeamSettings"
            >
              ×
            </button>
          </header>

          <div class="team-search-wrap">
            <input
              v-model="teamSearch"
              class="team-search"
              type="search"
              placeholder="チーム名・リーグ名で検索"
              aria-label="チームを検索"
            >
          </div>

          <div class="league-options league-options--teams">
            <button
              type="button"
              class="league-option"
              :class="{ 'league-option--selected': isAllDraftTeamsSelected }"
              :aria-pressed="isAllDraftTeamsSelected"
              @click="selectAllDraftTeams"
            >
              <span>
                <strong>チーム指定なし</strong>
                <small>リーグ内の全試合を表示</small>
              </span>
              <span class="league-option__check" aria-hidden="true">
                {{ isAllDraftTeamsSelected ? '✓' : '' }}
              </span>
            </button>

            <button
              v-for="team in filteredTeamOptions"
              :key="team.id"
              type="button"
              class="league-option"
              :class="{ 'league-option--selected': draftTeams.has(team.id) }"
              :aria-pressed="draftTeams.has(team.id)"
              @click="toggleDraftTeam(team.id)"
            >
              <span>
                <strong>{{ team.name }}</strong>
                <small>{{ team.competitions.join(' · ') }}</small>
              </span>
              <span class="league-option__check" aria-hidden="true">
                {{ draftTeams.has(team.id) ? '✓' : '' }}
              </span>
            </button>

            <p v-if="filteredTeamOptions.length === 0" class="team-search-empty">
              該当するチームがありません。
            </p>
          </div>

          <footer class="league-modal__footer">
            <button type="button" class="modal-secondary-button" @click="closeTeamSettings">
              キャンセル
            </button>
            <button type="button" class="modal-primary-button" @click="saveTeamSettings">
              完了
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </main>
</template>