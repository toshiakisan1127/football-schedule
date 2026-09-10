export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  css: ['~/assets/css/main.css'],
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
