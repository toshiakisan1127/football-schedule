import tailwindcss from '@tailwindcss/vite'

const siteUrl = 'https://dus59dgj79li1.cloudfront.net/'
const siteTitle = 'サッカー試合日程｜プレミアリーグ・ラ・リーガを日本時間で確認'
const siteDescription = 'プレミアリーグとラ・リーガの試合日程を日本時間で見やすく確認。今日・明日・今週末や好きなチーム、日本人選手所属チームで絞り込める無料のサッカー日程アプリ。'
const ogImageUrl = new URL('og-image.svg', siteUrl).toString()

export default defineNuxtConfig({
  ssr: true,
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
      title: siteTitle,
      meta: [
        {
          name: 'description',
          content: siteDescription,
        },
        {
          name: 'robots',
          content: 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1',
        },
        { property: 'og:title', content: siteTitle },
        { property: 'og:description', content: siteDescription },
        { property: 'og:type', content: 'website' },
        { property: 'og:url', content: siteUrl },
        { property: 'og:image', content: ogImageUrl },
        { property: 'og:image:type', content: 'image/svg+xml' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { property: 'og:site_name', content: 'サッカー試合日程' },
        { property: 'og:locale', content: 'ja_JP' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:title', content: siteTitle },
        { name: 'twitter:description', content: siteDescription },
        { name: 'twitter:image', content: ogImageUrl },
        { name: 'theme-color', content: '#0c1117' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
        { name: 'apple-mobile-web-app-title', content: 'サッカー日程' },
      ],
      link: [
        { rel: 'canonical', href: siteUrl },
        { rel: 'manifest', href: '/manifest.webmanifest' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
      ],
      script: [
        {
          type: 'application/ld+json',
          innerHTML: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebApplication',
            name: 'サッカー試合日程',
            url: siteUrl,
            description: siteDescription,
            applicationCategory: 'SportsApplication',
            operatingSystem: 'Any',
            inLanguage: 'ja-JP',
            isAccessibleForFree: true,
          }),
        },
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
      description: 'プレミアリーグとラ・リーガの試合日程を日本時間で見やすく確認できるアプリ。',
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
