import { createApp } from 'vue'
import OnboardingModal from '../components/OnboardingModal.vue'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook('app:mounted', () => {
    if (document.getElementById('football-schedule-onboarding-root')) return

    const container = document.createElement('div')
    container.id = 'football-schedule-onboarding-root'
    document.body.appendChild(container)

    createApp(OnboardingModal).mount(container)
  })
})
