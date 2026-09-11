<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

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
const headingRef = ref<HTMLElement | null>(null)

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

const openTutorial = async () => {
  currentStep.value = 0
  isOpen.value = true
  await nextTick()
  headingRef.value?.focus()
}

const finishOnboarding = () => {
  try {
    localStorage.setItem(STORAGE_KEY, String(ONBOARDING_VERSION))
  } catch {
    // Browsing contexts with restricted storage can still finish the tutorial.
  }

  isOpen.value = false
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
    isOpen.value = true
  }
})
</script>

<template>
  <Teleport to=".header-actions">
    <button
      type="button"
      class="tutorial-launcher"
      aria-label="使い方チュートリアルを開く"
      title="使い方チュートリアル"
      @click="openTutorial"
    >
      🔰
    </button>
  </Teleport>

  <BottomSheet
    :open="isOpen"
    :labelledby="`tutorial-title-${currentStep}`"
    :describedby="`tutorial-description-${currentStep}`"
    size="half"
    @close="finishOnboarding"
  >
    <template #header>
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
    </template>

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

    <template #footer>
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
          type="button"
          class="tutorial-primary"
          @click="nextStep"
        >
          {{ isLastStep ? 'チュートリアルを完了' : '次へ' }}
        </button>
      </footer>
    </template>
  </BottomSheet>
</template>

<style scoped>
.tutorial-launcher {
  display: grid;
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  padding: 0;
  background: var(--surface);
  color: var(--text);
  font-size: 0.88rem;
  line-height: 1;
  cursor: pointer;
}

.tutorial-launcher:hover {
  background: var(--surface-muted);
}

.tutorial-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 9px 20px 12px;
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
  border: 0;
  padding: 6px 0 6px 12px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.74rem;
  font-weight: 700;
  cursor: pointer;
}

.tutorial-progress {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 0;
  padding: 10px 20px 12px;
  border-top: 1px solid var(--border);
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
  padding: 24px 22px 28px;
}

.tutorial-step-label {
  margin-bottom: 7px;
  color: var(--text-muted);
  font-size: 0.64rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.tutorial-title {
  margin: 0 0 10px;
  font-size: clamp(1.22rem, 4.6vw, 1.55rem);
  line-height: 1.32;
  outline: none;
}

.tutorial-description {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.88rem;
  line-height: 1.7;
}

.tutorial-points {
  display: grid;
  gap: 10px;
  margin: 20px 0 0;
  padding: 0;
  list-style: none;
}

.tutorial-points li {
  position: relative;
  padding-left: 20px;
  font-size: 0.82rem;
  line-height: 1.55;
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
  padding: 12px 18px calc(12px + env(safe-area-inset-bottom));
}

.tutorial-primary,
.tutorial-secondary {
  min-height: 42px;
  border-radius: 10px;
  padding: 0 17px;
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

.tutorial-launcher:focus-visible,
.tutorial-primary:focus-visible,
.tutorial-secondary:focus-visible,
.tutorial-close:focus-visible {
  outline: 2px solid var(--text);
  outline-offset: 3px;
}

@media (max-width: 560px) {
  .tutorial-launcher {
    width: 28px;
    height: 28px;
    font-size: 0.82rem;
  }

  .tutorial-header,
  .tutorial-progress,
  .tutorial-footer {
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
    padding: 22px 18px 24px;
  }
}
</style>
