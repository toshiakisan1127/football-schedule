<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type OnboardingSlide = {
  label: string
  title: string
  description: string
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
        label: 'ホーム画面',
        title: 'ホーム画面からそのまま使えます',
        description: 'この端末ではすでにPWAとして起動しています。ホーム画面のMatch Calendarから、いつでも試合日程を開けます。',
        points: [
          'ブラウザを開かずに起動できます',
          '必要なときは右下の↻で再読み込みできます',
        ],
      }
    : isIOS.value
      ? {
          label: 'ホーム画面',
          title: '必要ならホーム画面に追加できます',
          description: 'iPhoneではSafariの共有メニューから「ホーム画面に追加」を選ぶと、アプリのように起動できます。',
          points: [
            'Safariの共有ボタンを開きます',
            '「ホーム画面に追加」を選びます',
          ],
        }
      : {
          label: 'ホーム画面',
          title: '必要ならアプリとして追加できます',
          description: '対応ブラウザでは、インストールや「ホーム画面に追加」からMatch Calendarをアプリのように使えます。',
          points: [
            'ブラウザのインストール / ホーム画面追加を選びます',
            '追加後はアプリアイコンから起動できます',
          ],
        }

  return [
    {
      label: 'このサイト',
      title: '試合日程を日本時間で確認できます',
      description: '欧州・日本のサッカー日程をまとめて確認するためのサイトです。試合時間は日本時間で表示します。',
      points: [
        '複数リーグ・大会の日程をまとめて確認',
        '今日・明日・今週末で絞り込み',
        '試合結果は必要なときだけ表示',
      ],
    },
    {
      label: '絞り込み',
      title: '見たい試合だけに絞り込めます',
      description: '表示するリーグや複数のお気に入りチームを選べます。日本人選手の所属チームだけを表示することもできます。',
      points: [
        '表示するリーグを選択',
        '複数のお気に入りチームを設定',
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
    // Browsing contexts with restricted storage can still finish the tutorial.
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
    <div v-if="isOpen" class="tutorial-backdrop">
      <section
        ref="dialogRef"
        class="tutorial-modal"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`tutorial-title-${currentStep}`"
        :aria-describedby="`tutorial-description-${currentStep}`"
      >
        <header class="tutorial-header">
          <div>
            <p class="tutorial-kicker">使い方チュートリアル</p>
            <p class="tutorial-step-count">{{ currentStep + 1 }} / {{ slides.length }}</p>
          </div>
          <button type="button" class="tutorial-close" @click="finishOnboarding">
            閉じる
          </button>
        </header>

        <ol class="tutorial-progress" aria-label="チュートリアルの進捗">
          <li
            v-for="(slide, index) in slides"
            :key="slide.label"
            class="tutorial-progress__item"
            :class="{
              'tutorial-progress__item--active': index === currentStep,
              'tutorial-progress__item--done': index < currentStep,
            }"
            :aria-current="index === currentStep ? 'step' : undefined"
          >
            <span class="tutorial-progress__number">{{ index + 1 }}</span>
            <span>{{ slide.label }}</span>
          </li>
        </ol>

        <div class="tutorial-content">
          <p class="tutorial-step-label">STEP {{ currentStep + 1 }}</p>
          <h2
            :id="`tutorial-title-${currentStep}`"
            ref="headingRef"
            class="tutorial-title"
            tabindex="-1"
          >
            {{ currentSlide.title }}
          </h2>
          <p :id="`tutorial-description-${currentStep}`" class="tutorial-description">
            {{ currentSlide.description }}
          </p>

          <ul class="tutorial-points">
            <li v-for="point in currentSlide.points" :key="point">{{ point }}</li>
          </ul>
        </div>

        <footer class="tutorial-footer">
          <button
            v-if="currentStep > 0"
            type="button"
            class="tutorial-secondary"
            @click="previousStep"
          >
            戻る
          </button>
          <span v-else />

          <button
            ref="primaryButtonRef"
            type="button"
            class="tutorial-primary"
            @click="nextStep"
          >
            {{ isLastStep ? 'チュートリアルを完了' : '次へ' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.tutorial-backdrop {
  position: fixed;
  z-index: 2000;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(0 0 0 / 48%);
}

.tutorial-modal {
  width: min(460px, 100%);
  overflow: hidden;
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 18px 55px rgb(0 0 0 / 30%);
}

.tutorial-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid var(--border);
}

.tutorial-kicker,
.tutorial-step-count,
.tutorial-step-label {
  margin: 0;
}

.tutorial-kicker {
  font-size: 0.82rem;
  font-weight: 800;
}

.tutorial-step-count {
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
}

.tutorial-close {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 6px 10px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

.tutorial-progress {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin: 0;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border);
  list-style: none;
}

.tutorial-progress__item {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  color: var(--text-subtle);
  font-size: 0.68rem;
  font-weight: 700;
}

.tutorial-progress__number {
  display: grid;
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  place-items: center;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  font-size: 0.65rem;
  font-variant-numeric: tabular-nums;
}

.tutorial-progress__item--active {
  color: var(--text);
}

.tutorial-progress__item--active .tutorial-progress__number,
.tutorial-progress__item--done .tutorial-progress__number {
  border-color: var(--active-bg);
  background: var(--active-bg);
  color: var(--active-text);
}

.tutorial-content {
  padding: 22px 22px 20px;
}

.tutorial-step-label {
  margin-bottom: 6px;
  color: var(--text-muted);
  font-size: 0.64rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.tutorial-title {
  margin: 0 0 9px;
  font-size: 1.25rem;
  line-height: 1.3;
  outline: none;
}

.tutorial-description {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.86rem;
  line-height: 1.65;
}

.tutorial-points {
  display: grid;
  gap: 8px;
  margin: 18px 0 0;
  padding: 0;
  list-style: none;
}

.tutorial-points li {
  position: relative;
  padding-left: 20px;
  font-size: 0.8rem;
  line-height: 1.5;
}

.tutorial-points li::before {
  position: absolute;
  top: 0;
  left: 0;
  color: var(--text-muted);
  content: '•';
  font-weight: 900;
}

.tutorial-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px calc(14px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
}

.tutorial-primary,
.tutorial-secondary {
  min-height: 40px;
  border-radius: 9px;
  padding: 0 16px;
  font-size: 0.8rem;
  font-weight: 750;
  cursor: pointer;
}

.tutorial-primary {
  border: 1px solid var(--active-bg);
  background: var(--active-bg);
  color: var(--active-text);
}

.tutorial-secondary {
  border: 1px solid var(--border-strong);
  background: transparent;
  color: var(--text);
}

.tutorial-primary:focus-visible,
.tutorial-secondary:focus-visible,
.tutorial-close:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 3px;
}

@media (max-width: 560px) {
  .tutorial-backdrop {
    align-items: end;
    padding: 0;
  }

  .tutorial-modal {
    width: 100%;
    border-right: 0;
    border-bottom: 0;
    border-left: 0;
    border-radius: 16px 16px 0 0;
  }

  .tutorial-header {
    padding-top: 14px;
  }

  .tutorial-progress {
    padding-inline: 16px;
  }

  .tutorial-progress__item {
    gap: 4px;
    font-size: 0.62rem;
  }

  .tutorial-progress__number {
    width: 18px;
    height: 18px;
  }

  .tutorial-content {
    padding: 20px 18px 18px;
  }
}
</style>
