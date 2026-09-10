<script setup lang="ts">
import type { Fixture, FixtureDocument } from './types/fixture'

const runtimeConfig = useRuntimeConfig()
const baseURL = runtimeConfig.app.baseURL.endsWith('/')
  ? runtimeConfig.app.baseURL
  : `${runtimeConfig.app.baseURL}/`

const { data, status, error } = await useFetch<FixtureDocument>(`${baseURL}data/fixtures.json`, {
  server: false,
})

const localDateKey = (iso: string) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(iso))

  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('year')}-${get('month')}-${get('day')}`
}

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

const groupedFixtures = computed(() => {
  const fixtures = [...(data.value?.fixtures ?? [])].sort(
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
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(data.value.generatedAt))
})
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div>
        <p class="eyebrow">FOOTBALL SCHEDULE</p>
        <h1>試合日程</h1>
        <p class="subtitle">Jリーグと欧州サッカーの、試合時間だけ。</p>
      </div>

      <p v-if="generatedAtLabel" class="updated-at">
        最終更新 {{ generatedAtLabel }}
      </p>
    </header>

    <nav class="quick-filters" aria-label="日付フィルター">
      <button type="button" class="filter-button filter-button--active">今日</button>
      <button type="button" class="filter-button">明日</button>
      <button type="button" class="filter-button">今週末</button>
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
        表示できる試合がありません。
      </p>
    </section>
  </main>
</template>
