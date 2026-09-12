<script setup lang="ts">
import type { Fixture, LiveFixtureEvent } from '../types/fixture'
import { japanesePlayersForTeam } from '../data/japanesePlayers'

const props = defineProps<{
  fixture: Fixture
  showResults: boolean
}>()

const FIXTURE_TIME_ZONE = 'Asia/Tokyo'
const expanded = ref(false)

const hasJapanesePlayer = (name: string) => japanesePlayersForTeam(name).length > 0

const teamDisplayName = (name: string) =>
  hasJapanesePlayer(name) ? `${name} 🇯🇵` : name

const japanesePlayersTitle = (name: string) => {
  const players = japanesePlayersForTeam(name)
  return players.length > 0 ? `日本人選手: ${players.join('、')}` : undefined
}

const handleTeamLogoError = (event: Event) => {
  const target = event.currentTarget
  if (target instanceof HTMLImageElement) {
    target.hidden = true
  }
}

const timeLabel = (iso: string) =>
  new Intl.DateTimeFormat('ja-JP', {
    timeZone: FIXTURE_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))

const displayedEvents = computed(() =>
  (props.fixture.live?.events ?? []).filter((event) =>
    event.type === 'goal' || event.type === 'card' || event.type === 'substitution',
  ),
)

const expandable = computed(() =>
  props.fixture.status === 'live' && displayedEvents.value.length > 0,
)

const liveLabel = computed(() => {
  const live = props.fixture.live
  if (!live) return null
  const extra = live.extra ? `+${live.extra}` : ''
  return `LIVE ${live.elapsed}${extra}'`
})

const liveScoreLabel = computed(() => {
  if (props.fixture.status !== 'live' || !props.fixture.score) return null
  return `${props.fixture.score.home}–${props.fixture.score.away}`
})

const resultLabel = computed(() => {
  if (!props.showResults || props.fixture.status !== 'finished' || !props.fixture.score) return null
  return `${props.fixture.score.home}–${props.fixture.score.away}`
})

const statusLabel = computed(() => {
  if (props.fixture.status === 'postponed') return '延期'
  if (props.fixture.status === 'cancelled') return '中止'
  return null
})

const toggleDetails = () => {
  if (!expandable.value) return
  expanded.value = !expanded.value
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!expandable.value || (event.key !== 'Enter' && event.key !== ' ')) return
  event.preventDefault()
  toggleDetails()
}

const eventMinute = (event: LiveFixtureEvent) =>
  `${event.elapsed}${event.extra ? `+${event.extra}` : ''}'`

const eventIcon = (event: LiveFixtureEvent) => {
  if (event.type === 'goal') {
    return event.detail?.toLowerCase().includes('missed') ? '❌' : '⚽'
  }
  if (event.type === 'card') {
    return event.detail?.toLowerCase().includes('red') ? '🟥' : '🟨'
  }
  if (event.type === 'substitution') return '↔'
  return '•'
}

const eventLabel = (event: LiveFixtureEvent) => {
  if (event.type === 'substitution') {
    return `${event.player ?? '選手'} → ${event.assist ?? '選手'}`
  }
  return event.player ?? '選手情報なし'
}

const eventDetailLabel = (event: LiveFixtureEvent) => {
  if (event.type === 'goal') {
    if (event.detail === 'Penalty') return 'PK'
    if (event.detail === 'Missed Penalty') return 'PK失敗'
    if (event.detail === 'Own Goal') return 'オウンゴール'
    if (event.detail === 'Normal Goal') return null
    return event.detail
  }
  if (event.type === 'card') return event.comments
  return null
}

watch(() => props.fixture.status, (status) => {
  if (status !== 'live') expanded.value = false
})
</script>

<template>
  <div class="fixture-item" :class="{ 'fixture-item--live': fixture.status === 'live' }">
    <div
      class="fixture-row"
      :class="{ 'fixture-row--expandable': expandable }"
      :role="expandable ? 'button' : undefined"
      :tabindex="expandable ? 0 : undefined"
      :aria-expanded="expandable ? expanded : undefined"
      :aria-label="expandable ? `${fixture.home.name} 対 ${fixture.away.name} のLIVEイベントを${expanded ? '閉じる' : '開く'}` : undefined"
      @click="toggleDetails"
      @keydown="handleKeydown"
    >
      <time :datetime="fixture.kickoff" class="kickoff">
        {{ timeLabel(fixture.kickoff) }}
      </time>

      <div class="fixture-main">
        <p class="competition">
          {{ fixture.competition.country }} · {{ fixture.competition.name }}
        </p>
        <p class="matchup">
          <span class="team-name" :title="japanesePlayersTitle(fixture.home.name)">
            <img
              v-if="fixture.home.logo"
              class="team-logo"
              :src="fixture.home.logo"
              :alt="`${fixture.home.name} ロゴ`"
              width="18"
              height="18"
              loading="lazy"
              decoding="async"
              @error="handleTeamLogoError"
            >
            <span>{{ teamDisplayName(fixture.home.name) }}</span>
          </span>
          <span class="versus">vs</span>
          <span class="team-name" :title="japanesePlayersTitle(fixture.away.name)">
            <img
              v-if="fixture.away.logo"
              class="team-logo"
              :src="fixture.away.logo"
              :alt="`${fixture.away.name} ロゴ`"
              width="18"
              height="18"
              loading="lazy"
              decoding="async"
              @error="handleTeamLogoError"
            >
            <span>{{ teamDisplayName(fixture.away.name) }}</span>
          </span>
        </p>
      </div>

      <div
        class="fixture-side"
        :class="{ 'fixture-side--live': fixture.status === 'live' && fixture.live }"
      >
        <template v-if="fixture.status === 'live' && fixture.live">
          <span v-if="liveScoreLabel" class="fixture-live-score">
            {{ liveScoreLabel }}
          </span>
          <span v-if="liveLabel" class="fixture-status fixture-status--live">
            {{ liveLabel }}
          </span>
        </template>
        <span v-else-if="resultLabel" class="fixture-result">
          {{ resultLabel }}
        </span>
        <span v-else-if="statusLabel" class="fixture-status">
          {{ statusLabel }}
        </span>
      </div>
    </div>

    <div v-if="expanded && displayedEvents.length > 0" class="live-events">
      <p class="live-events__hint">LIVEイベント</p>
      <div
        v-for="(event, index) in displayedEvents"
        :key="`${event.elapsed}-${event.extra ?? 0}-${event.type}-${index}`"
        class="live-event"
      >
        <span class="live-event__minute">{{ eventMinute(event) }}</span>
        <span class="live-event__icon" aria-hidden="true">{{ eventIcon(event) }}</span>
        <span class="live-event__label">
          {{ eventLabel(event) }}
          <span v-if="eventDetailLabel(event)" class="live-event__detail">
            · {{ eventDetailLabel(event) }}
          </span>
        </span>
      </div>
    </div>
  </div>
</template>
