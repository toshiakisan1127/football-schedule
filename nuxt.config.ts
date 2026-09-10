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
      title: 'サッカー試合日程 | Football Schedule',
      meta: [
        {
          name: 'description',
          content: 'サッカーの試合日程を日本時間で見やすく確認できるアプリ。現在はプレミアリーグに対応。',
        },
      ],
    },
  },
  nitro: {
    preset: 'static',
  },
  compatibilityDate: '2026-09-10',
})
