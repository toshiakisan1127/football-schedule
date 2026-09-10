<script setup lang="ts">
import type { Fixture, FixtureDocument } from './types/fixture'

type DateFilter = 'all' | 'today' | 'tomorrow' | 'weekend'
type Theme = 'light' | 'dark'

const runtimeConfig = useRuntimeConfig()
const baseURL = runtimeConfig.app.baseURL.endsWith('/')
  ? runtimeConfig.app.baseURL
  : `${runtimeConfig.app.baseURL}/`

const mockDataVersion = '20260911-003'
const fixturesUrl = `${baseURL}data/fixtures.json?v=${mockDataVersion}`

const { data, status, error } = await useFetch<FixtureDocument>(fixturesUrl, {
  server: false,
  cache: 'no-store',
})

const selectedFilter = ref<DateFilter>('all')
const selectedCompetition = ref('all')
const currentDate = ref<Date | null>(null)
const theme = ref<Theme>('dark')

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

  return [
    { id: 'all', name: '全リーグ', country: '' },
    ...[...competitions.values()].sort((a, b) =>
      `${a.country}-${a.name}`.localeCompare(`${b.country}-${b.name}`),
    ),
  ]
})

const selectedCompetitionLabel = computed(() =>
  competitionFilters.value.find((competition) => competition.id === selectedCompetition.value)?.name ?? '全リーグ',
)

const localDateKeyFromDate = (date: Date) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)

  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

const localDateKey = (iso: string) => localDateKeyFromDate(new Date(iso))

const addDays = (date: Date, days: number) => {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

const targetDateKeys = computed(() => {
  if (selectedFilter.value === 'all') return null
  if (!currentDate.value) return new Set<string>()

  const today = new Date(
    currentDate.value.getFullYear(),
    currentDate.value.getMonth(),
    currentDate.value.getDate(),
  )

  if (selectedFilter.value === 'today') {
    return new Set([localDateKeyFromDate(today)])
  }

  if (selectedFilter.value === 'tomorrow') {
    return new Set([localDateKeyFromDate(addDays(today, 1))])
  }

  const dayOfWeek = today.getDay()
  const saturdayOffset = dayOfWeek === 0 ? -1 : 6 - dayOfWeek
  const saturday = addDays(today, saturdayOffset)
  const sunday = addDays(saturday, 1)

  return new Set([
    localDateKeyFromDate(saturday),
    localDateKeyFromDate(sunday),
  ])
})

const dateLabel = (iso: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date(iso))

const timeLabel = (iso: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))

const statusLabel = (fixture: Fixture) => {
  if (fixture.status === 'postponed') return '延期'
  if (fixture.status === 'cancelled') return '中止'
  return null
}

const filteredFixtures = computed(() => {
  let fixtures = data.value?.fixtures ?? []

  if (selectedCompetition.value !== 'all') {
    fixtures = fixtures.filter((fixture) => fixture.competition.id === selectedCompetition.value)
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
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(data.value.generatedAt))
})

const emptyMessage = computed(() => {
  const competitionPrefix = selectedCompetition.value === 'all'
    ? ''
    : `${selectedCompetitionLabel.value}の`

  if (selectedFilter.value === 'all') return `${competitionPrefix}表示できる試合がありません。`
  if (selectedFilter.value === 'today') return `${competitionPrefix}今日の試合はありません。`
  if (selectedFilter.value === 'tomorrow') return `${competitionPrefix}明日の試合はありません。`
  return `${competitionPrefix}今週末の試合はありません。`
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

onMounted(() => {
  currentDate.value = new Date()

  const savedTheme = localStorage.getItem('football-schedule-theme')
  const initialTheme: Theme = savedTheme === 'light' || savedTheme === 'dark'
    ? savedTheme
    : window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'

  applyTheme(initialTheme)
})
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div class="header-copy">
        <p class="eyebrow">FOOTBALL SCHEDULE</p>
        <h1>試合日程</h1>
        <p class="subtitle">Jリーグと欧州サッカーの、試合時間だけ。</p>
      </div>

      <div class="header-meta">
        <button
          type="button"
          class="theme-toggle"
          :aria-label="theme === 'dark' ? 'ライトモードに切り替える' : 'ダークモードに切り替える'"
          @click="toggleTheme"
        >
          {{ theme === 'dark' ? '☀︎ ライト' : '☾ ダーク' }}
        </button>
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

    <nav class="quick-filters quick-filters--league" aria-label="リーグフィルター">
      <button
        v-for="competition in competitionFilters"
        :key="competition.id"
        type="button"
        class="filter-button filter-button--league"
        :class="{ 'filter-button--active': selectedCompetition === competition.id }"
        :aria-pressed="selectedCompetition === competition.id"
        @click="selectedCompetition = competition.id"
      >
        {{ competition.name }}
      </button>
    </nav>

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

            <span v-if="statusLabel(fixture)" class="fixture-status">
              {{ statusLabel(fixture) }}
            </span>
          </div>
        </div>
      </article>

      <p v-if="groupedFixtures.length === 0" class="state-message">
        {{ emptyMessage }}
      </p>
    </section>
  </main>
</template>
