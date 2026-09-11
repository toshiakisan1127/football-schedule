<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type OnboardingSlide = {
  eyebrow: string
  title: string
  description: string
  icon: string
  points: string[]
}

const ONBOARDING_VERSION = 1
const STORAGE_KEY = 'football-schedule-onboarding-version'

const isOpen = ref(false)
const currentStep = ref(0)
const isStandalone = ref(false)
const isIOS = ref(false)
const dialogRef = ref<HTMLElement | null>(null)
const headingRef = ref<HTMLElement | null>(null)
const primaryButtonRef = ref<HTMLButtonElement | null>(null)
let previousBodyOverflow = ''

const slides = computed<OnboardingSlide[]>(() => {
  const pwaSlide: OnboardingSlide = isStandalone.value
    ? {
        eyebrow: 'APP MODE',
        title: 'ホーム画面から、すぐ試合日程へ',
        description: 'この端末ではすでにアプリとして起動しています。ブラウザを開かず、ホーム画面からMatch Calendarを使えます。',
        icon: '✓',
        points: [
          'フルスクリーンに近い感覚で使える',
          '日程は自動更新。必要な時は↻で再読み込み',
        ],
      }
    : isIOS.value
      ? {
          eyebrow: 'ADD TO HOME SCREEN',
          title: '最後に、ホーム画面へ追加できます',
          description: 'Safariの共有ボタンから「ホーム画面に追加」を選ぶと、Match Calendarをアプリのようにすぐ開けます。',
          icon: '↗',
          points: [
            'Safariの「共有」→「ホーム画面に追加」',
            '追加後はホーム画面のアイコンから起動',
          ],
        }
      : {
          eyebrow: 'INSTALL APP',
          title: '最後に、アプリとして追加できます',
          description: '対応ブラウザでは、インストールや「ホーム画面に追加」からMatch Calendarをアプリのように使えます。',
          icon: '＋',
          points: [
            'ブラウザのインストール / ホーム画面追加を選択',
            '追加後はアプリアイコンからすぐ起動',
          ],
        }

  return [
    {
      eyebrow: 'WELCOME TO MATCH CALENDAR',
      title: 'サッカーの予定を、日本時間ですぐ確認',
      description: '欧州・日本のサッカー日程をまとめて確認できるサイトです。試合時間は日本時間で表示するので、時差を計算する必要はありません。',
      icon: '⚽',
      points: [
        '複数リーグ・大会の日程をひとつに集約',
        '今日・明日・今週末の試合をすぐ確認',
        '試合結果は見たい時だけ表示',
      ],
    },
    {
      eyebrow: 'YOUR FIXTURES',
      title: '見たい試合だけに絞り込めます',
      description: 'リーグや複数のお気に入りチームを選んで、自分用の日程表にできます。日本人選手の所属チームだけを見ることもできます。',
      icon: '⌕',
      points: [
        'リーグごとに表示を切り替え',
        '複数のお気に入りチームをまとめて追える',
        '🇯🇵 日本人所属チームだけに絞り込み',
      ],
    },
    pwaSlide,
  ]
})

const currentSlide = computed(() => slides.value[currentStep.value] ?? slides.value[0]!)
const isLastStep = computed(() => currentStep.value === slides.value.length - 1)

const restoreBodyScroll = () => {
  document.body.style.overflow = previousBodyOverflow
}

const finishOnboarding = () => {
  try {
    localStorage.setItem(STORAGE_KEY, String(ONBOARDING_VERSION))
  } catch {
    // Browsing contexts with restricted storage can still finish the onboarding.
  }

  isOpen.value = false
  restoreBodyScroll()
}

const nextStep = async () => {
  if (isLastStep.value) {
    finishOnboarding()
    return
  }

  currentStep.value += 1
  await nextTick()
  headingRef.value?.focus()
}

const previousStep = async () => {
  if (currentStep.value === 0) return
  currentStep.value -= 1
  await nextTick()
  headingRef.value?.focus()
}

const focusableElements = () => {
  if (!dialogRef.value) return []

  return [...dialogRef.value.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )]
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!isOpen.value) return

  if (event.key === 'Escape') {
    event.preventDefault()
    finishOnboarding()
    return
  }

  if (event.key !== 'Tab') return

  const focusable = focusableElements()
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) return

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(isOpen, async (open) => {
  if (!open) return

  await nextTick()
  primaryButtonRef.value?.focus()
})

onMounted(() => {
  isStandalone.value = window.matchMedia('(display-mode: standalone)').matches
    || ('standalone' in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone))

  isIOS.value = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

  let savedVersion = 0
  try {
    savedVersion = Number.parseInt(localStorage.getItem(STORAGE_KEY) ?? '0', 10)
  } catch {
    savedVersion = 0
  }

  if (!Number.isFinite(savedVersion) || savedVersion < ONBOARDING_VERSION) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    isOpen.value = true
  }

  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (isOpen.value) restoreBodyScroll()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="onboarding-backdrop">
      <section
        ref="dialogRef"
        class="onboarding-modal"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`onboarding-title-${currentStep}`"
        :aria-describedby="`onboarding-description-${currentStep}`"
      >
        <header class="onboarding-header">
          <div class="onboarding-progress" aria-label="オンボーディング進捗">
            <span
              v-for="(_, index) in slides"
              :key="index"
              class="onboarding-dot"
              :class="{ 'onboarding-dot--active': index === currentStep }"
              :aria-current="index === currentStep ? 'step' : undefined"
            />
          </div>

          <button type="button" class="onboarding-skip" @click="finishOnboarding">
            スキップ
          </button>
        </header>

        <div class="onboarding-content">
          <div class="onboarding-icon" aria-hidden="true">{{ currentSlide.icon }}</div>
          <p class="onboarding-eyebrow">{{ currentSlide.eyebrow }}</p>
          <h2
            :id="`onboarding-title-${currentStep}`"
            ref="headingRef"
            class="onboarding-title"
            tabindex="-1"
          >
            {{ currentSlide.title }}
          </h2>
          <p :id="`onboarding-description-${currentStep}`" class="onboarding-description">
            {{ currentSlide.description }}
          </p>

          <ul class="onboarding-points">
            <li v-for="point in currentSlide.points" :key="point">{{ point }}</li>
          </ul>
        </div>

        <footer class="onboarding-footer">
          <button
            v-if="currentStep > 0"
            type="button"
            class="onboarding-secondary"
            @click="previousStep"
          >
            戻る
          </button>
          <span v-else class="onboarding-step-count">{{ currentStep + 1 }} / {{ slides.length }}</span>

          <button
            ref="primaryButtonRef"
            type="button"
            class="onboarding-primary"
            @click="nextStep"
          >
            {{ isLastStep ? 'はじめる' : '次へ' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.onboarding-backdrop {
  position: fixed;
  z-index: 2000;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(0 0 0 / 64%);
  backdrop-filter: blur(5px);
}

.onboarding-modal {
  width: min(430px, 100%);
  overflow: hidden;
  border: 1px solid var(--border-strong);
  border-radius: 22px;
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 28px 90px rgb(0 0 0 / 42%);
}

.onboarding-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px 0;
}

.onboarding-progress {
  display: flex;
  gap: 6px;
}

.onboarding-dot {
  width: 18px;
  height: 4px;
  border-radius: 999px;
  background: var(--border-strong);
  transition: width 160ms ease, background-color 160ms ease;
}

.onboarding-dot--active {
  width: 32px;
  background: var(--text);
}

.onboarding-skip {
  border: 0;
  padding: 6px 0;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
}

.onboarding-content {
  padding: 24px 24px 20px;
}

.onboarding-icon {
  display: grid;
  width: 56px;
  height: 56px;
  margin-bottom: 18px;
  place-items: center;
  border: 1px solid var(--border-strong);
  border-radius: 18px;
  background: var(--surface-muted);
  font-size: 1.65rem;
  font-weight: 800;
}

.onboarding-eyebrow {
  margin: 0 0 7px;
  color: var(--text-muted);
  font-size: 0.64rem;
  font-weight: 800;
  letter-spacing: 0.11em;
}

.onboarding-title {
  margin: 0 0 10px;
  font-size: clamp(1.42rem, 6vw, 1.8rem);
  line-height: 1.18;
  letter-spacing: -0.025em;
  outline: none;
}

.onboarding-description {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
  line-height: 1.65;
}

.onboarding-points {
  display: grid;
  gap: 9px;
  margin: 20px 0 0;
  padding: 0;
  list-style: none;
}

.onboarding-points li {
  position: relative;
  padding-left: 22px;
  font-size: 0.82rem;
  font-weight: 650;
  line-height: 1.45;
}

.onboarding-points li::before {
  position: absolute;
  top: 0.05em;
  left: 0;
  color: var(--text-muted);
  content: '✓';
  font-weight: 900;
}

.onboarding-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px calc(16px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
}

.onboarding-primary,
.onboarding-secondary {
  min-height: 42px;
  border-radius: 11px;
  padding: 0 18px;
  font-size: 0.82rem;
  font-weight: 800;
  cursor: pointer;
}

.onboarding-primary {
  min-width: 112px;
  border: 1px solid var(--active-bg);
  background: var(--active-bg);
  color: var(--active-text);
}

.onboarding-secondary {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: var(--text);
}

.onboarding-step-count {
  color: var(--text-subtle);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.onboarding-primary:focus-visible,
.onboarding-secondary:focus-visible,
.onboarding-skip:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 3px;
}

@media (max-width: 560px) {
  .onboarding-backdrop {
    align-items: end;
    padding: 0;
  }

  .onboarding-modal {
    width: 100%;
    border-right: 0;
    border-bottom: 0;
    border-left: 0;
    border-radius: 22px 22px 0 0;
  }

  .onboarding-content {
    padding: 22px 20px 18px;
  }

  .onboarding-icon {
    width: 52px;
    height: 52px;
    margin-bottom: 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .onboarding-dot {
    transition: none;
  }
}
</style>
