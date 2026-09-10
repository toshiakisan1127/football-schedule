import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  css: [
    '~/assets/css/tailwind.css',
    '~/assets/css/main.css',
  ],
  vite: {
    plugins: [tailwindcss()],
  },
  app: {
    head: {
      htmlAttrs: { lang: 'ja' },
      title: 'Football Schedule',
      meta: [
        {
          name: 'description',
          content: 'Jリーグと欧州サッカーの試合日程を、見やすく確認するためのアプリ',
        },
      ],
    },
  },
  nitro: {
    preset: 'static',
  },
  compatibilityDate: '2026-09-10',
})
