<script setup lang="ts">
import type { LiveFixtureEvent } from '../types/fixture'

const props = defineProps<{
  events: LiveFixtureEvent[]
}>()

const timeLabel = (event: LiveFixtureEvent) => {
  if (event.elapsed === null) return '–'
  return event.extra ? `${event.elapsed}+${event.extra}'` : `${event.elapsed}'`
}

const detailKey = (event: LiveFixtureEvent) => event.detail?.trim().toLowerCase() ?? ''

const eventIcon = (event: LiveFixtureEvent) => {
  const detail = detailKey(event)

  if (event.type === 'goal') {
    return detail.includes('missed penalty') || detail.includes('cancelled') ? '✕' : '⚽'
  }
  if (event.type === 'substitution') return '↔'
  if (event.type === 'var') return '↺'
  return detail.includes('red') ? '🟥' : '🟨'
}

const goalLabel = (event: LiveFixtureEvent) => {
  const detail = detailKey(event)
  if (detail.includes('missed penalty')) return 'PK失敗'
  if (detail.includes('own goal')) return 'オウンゴール'
  if (detail === 'penalty') return 'PK'
  if (detail.includes('cancelled')) return 'ゴール取消'
  return null
}

const cardLabel = (event: LiveFixtureEvent) => {
  const detail = detailKey(event)
  if (detail.includes('yellow-red')) return '2枚目のイエロー'
  if (detail.includes('red')) return 'レッドカード'
  if (detail.includes('yellow')) return 'イエローカード'
  return event.detail ?? 'カード'
}

const varLabel = (event: LiveFixtureEvent) => {
  const detail = detailKey(event)
  if (detail.includes('goal cancelled')) return 'VAR · ゴール取消'
  if (detail.includes('goal confirmed')) return 'VAR · ゴール確認'
  if (detail.includes('penalty cancelled')) return 'VAR · PK取消'
  if (detail.includes('penalty confirmed')) return 'VAR · PK判定'
  return event.detail ? `VAR · ${event.detail}` : 'VAR'
}

const eventText = (event: LiveFixtureEvent) => {
  if (event.type === 'substitution') {
    if (event.player && event.assist) return `${event.player} → ${event.assist}`
    return event.player ?? event.assist ?? '交代'
  }

  if (event.type === 'var') return varLabel(event)

  if (event.type === 'goal') {
    const scorer = event.player ?? '得点'
    const playerLabel = event.assist ? `${scorer}（${event.assist}）` : scorer
    const label = goalLabel(event)
    return label ? `${playerLabel} · ${label}` : playerLabel
  }

  const player = event.player ?? 'カード'
  return `${player} · ${cardLabel(event)}`
}

const eventDetail = (event: LiveFixtureEvent) => event.teamName
</script>

<template>
  <div class="live-events" @click.stop>
    <p v-if="props.events.length === 0" class="live-events__empty">
      イベント情報はまだありません
    </p>
    <ol v-else class="live-events__list" aria-label="試合中イベント">
      <li v-for="(event, index) in props.events" :key="`${event.elapsed}-${event.type}-${index}`" class="live-event">
        <time class="live-event__time">{{ timeLabel(event) }}</time>
        <span class="live-event__icon" aria-hidden="true">{{ eventIcon(event) }}</span>
        <span class="live-event__body">
          <strong>{{ eventText(event) }}</strong>
          <small v-if="eventDetail(event)">{{ eventDetail(event) }}</small>
        </span>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.live-events {
  grid-column: 1 / -1;
  margin-left: 58px;
  padding-top: 9px;
  border-top: 1px solid var(--border);
}

.live-events__list {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.live-event {
  display: grid;
  grid-template-columns: 42px 18px minmax(0, 1fr);
  gap: 6px;
  align-items: start;
  font-size: 0.75rem;
}

.live-event__time {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.live-event__icon {
  line-height: 1.2;
  text-align: center;
}

.live-event__body {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.live-event__body strong {
  overflow: hidden;
  color: var(--text);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.live-event__body small,
.live-events__empty {
  color: var(--text-muted);
  font-size: 0.68rem;
}

.live-events__empty {
  margin: 0;
}

@media (max-width: 560px) {
  .live-events {
    margin-left: 0;
  }
}
</style>
