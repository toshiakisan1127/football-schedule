<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

type SheetSize = 'half' | 'large' | 'auto'

const props = withDefaults(defineProps<{
  open: boolean
  labelledby?: string
  describedby?: string
  size?: SheetSize
  closeOnBackdrop?: boolean
}>(), {
  labelledby: undefined,
  describedby: undefined,
  size: 'half',
  closeOnBackdrop: false,
})

const emit = defineEmits<{
  close: []
}>()

const sheetRef = ref<HTMLElement | null>(null)
let previousBodyOverflow = ''

const focusableElements = () => {
  if (!sheetRef.value) return []

  return [...sheetRef.value.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )]
}

const requestClose = () => {
  emit('close')
}

const handleBackdropClick = () => {
  if (props.closeOnBackdrop) requestClose()
}

const handleKeydown = (event: KeyboardEvent) => {
  if (!props.open) return

  if (event.key === 'Escape') {
    event.preventDefault()
    requestClose()
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

watch(() => props.open, async (open) => {
  if (open) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeydown)
    await nextTick()
    sheetRef.value?.focus()
    return
  }

  document.body.style.overflow = previousBodyOverflow
  document.removeEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (props.open) document.body.style.overflow = previousBodyOverflow
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="bottom-sheet-backdrop"
      @click.self="handleBackdropClick"
    >
      <section
        ref="sheetRef"
        class="bottom-sheet"
        :class="`bottom-sheet--${size}`"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="labelledby"
        :aria-describedby="describedby"
        tabindex="-1"
      >
        <div class="bottom-sheet__handle" aria-hidden="true" />

        <div v-if="$slots.header" class="bottom-sheet__header">
          <slot name="header" />
        </div>

        <div class="bottom-sheet__content">
          <slot />
        </div>

        <div v-if="$slots.footer" class="bottom-sheet__footer">
          <slot name="footer" />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.bottom-sheet-backdrop {
  position: fixed;
  z-index: 2000;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgb(0 0 0 / 34%);
}

.bottom-sheet {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  width: min(620px, 100%);
  overflow: hidden;
  border: 1px solid var(--border-strong);
  border-bottom: 0;
  border-radius: 22px 22px 0 0;
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 -10px 36px rgb(0 0 0 / 18%);
  outline: none;
  animation: bottom-sheet-in 180ms ease-out;
}

.bottom-sheet--half {
  height: min(62dvh, 610px);
  min-height: 430px;
}

.bottom-sheet--large {
  height: min(82dvh, 760px);
  min-height: 520px;
}

.bottom-sheet--auto {
  max-height: min(82dvh, 760px);
}

.bottom-sheet__handle {
  width: 38px;
  height: 4px;
  margin: 9px auto 2px;
  border-radius: 999px;
  background: var(--border-strong);
}

.bottom-sheet__header {
  min-width: 0;
}

.bottom-sheet__content {
  min-height: 0;
  overflow-y: auto;
}

.bottom-sheet__footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
}

@keyframes bottom-sheet-in {
  from {
    transform: translateY(24px);
    opacity: 0.92;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@media (max-width: 560px) {
  .bottom-sheet {
    width: 100%;
    border-right: 0;
    border-left: 0;
  }

  .bottom-sheet--half {
    height: 62dvh;
    min-height: 420px;
  }
}

@media (max-height: 680px) {
  .bottom-sheet--half {
    height: 72dvh;
    min-height: 390px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bottom-sheet {
    animation: none;
  }
}
</style>
