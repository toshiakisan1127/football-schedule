import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  modules: ['@vite-pwa/nuxt'],
  css: [
    '~/assets/css/tailwind.css',
    '~/assets/css/main.css',
    '~/assets/css/team-filter.css',
    '~/assets/css/fixture-team-name.css',
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
        { name: 'theme-color', content: '#0c1117' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
        { name: 'apple-mobile-web-app-title', content: 'サッカー日程' },
      ],
      link: [
        { rel: 'manifest', href: '/manifest.webmanifest' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
      ],
    },
  },
  pwa: {
    registerType: 'autoUpdate',
    includeAssets: ['favicon-32x32.png', 'apple-touch-icon.png'],
    manifest: {
      id: '/',
      name: 'サッカー試合日程',
      short_name: 'サッカー日程',
      description: 'サッカーの試合日程を日本時間で見やすく確認できるアプリ。',
      lang: 'ja',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      background_color: '#0c1117',
      theme_color: '#0c1117',
      categories: ['sports'],
      icons: [
        {
          src: '/pwa-192x192.png',
          sizes: '192x192',
          type: 'image/png',
        },
        {
          src: '/pwa-512x512.png',
          sizes: '512x512',
          type: 'image/png',
        },
        {
          src: '/pwa-512x512.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'maskable',
        },
      ],
    },
    workbox: {
      cleanupOutdatedCaches: true,
      navigateFallback: '/index.html',
      globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
      runtimeCaching: [
        {
          urlPattern: /\/data\/.*\.json$/,
          handler: 'NetworkFirst',
          options: {
            cacheName: 'football-schedule-data',
            networkTimeoutSeconds: 3,
            cacheableResponse: {
              statuses: [0, 200],
            },
            expiration: {
              maxEntries: 10,
              maxAgeSeconds: 60 * 60 * 24,
            },
          },
        },
      ],
    },
    devOptions: {
      enabled: false,
    },
  },
  nitro: {
    preset: 'static',
  },
  compatibilityDate: '2026-09-10',
})
