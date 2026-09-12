<script setup lang="ts">
import type { LiveFixtureEvent } from '../types/fixture'

const props = defineProps<{
  events: LiveFixtureEvent[]
}>()

const timeLabel = (event: LiveFixtureEvent) => {
  if (event.elapsed === null) return '–'
  return event.extra ? `${event.elapsed}+${event.extra}'` : `${event.elapsed}'`
}

const eventIcon = (event: LiveFixtureEvent) => {
  if (event.type === 'goal') return '⚽'
  if (event.type === 'substitution') return '↔'
  return event.detail?.toLowerCase().includes('red') ? '🟥' : '🟨'
}

const eventText = (event: LiveFixtureEvent) => {
  if (event.type === 'substitution') {
    if (event.player && event.assist) return `${event.player} → ${event.assist}`
    return event.player ?? event.assist ?? '交代'
  }

  if (event.type === 'goal') {
    const scorer = event.player ?? '得点'
    return event.assist ? `${scorer}（${event.assist}）` : scorer
  }

  return event.player ?? event.detail ?? 'カード'
}

const eventDetail = (event: LiveFixtureEvent) => {
  if (event.type === 'card') return event.detail
  if (event.type === 'goal' && event.detail && event.detail !== 'Normal Goal') return event.detail
  return event.teamName
}
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
