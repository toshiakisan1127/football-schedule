import tailwindcss from '@tailwindcss/vite'

const siteUrl = 'https://dus59dgj79li1.cloudfront.net/'
const siteName = 'Match Calendar'
const siteTitle = 'Match Calendar｜欧州・日本のフットボール日程を日本時間で'
const siteDescription = '欧州と日本のフットボール日程を日本時間でシンプルに確認。今日・明日・今週末、好きなチーム、日本人選手所属チームで絞り込める無料の試合日程アプリ。'
const ogImageUrl = new URL('og-image.png', siteUrl).toString()
const brandColor = '#0F6B3A'
const themeInitScript = `(() => {
  try {
    const savedTheme = localStorage.getItem('football-schedule-theme')
    const theme = savedTheme === 'light' || savedTheme === 'dark'
      ? savedTheme
      : window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'

    document.documentElement.dataset.theme = theme
  } catch {
    // Keep the CSS prefers-color-scheme fallback when storage is unavailable.
  }
})()`

export default defineNuxtConfig({
  ssr: true,
  devtools: { enabled: true },
  modules: ['@vite-pwa/nuxt'],
  css: [
    '~/assets/css/tailwind.css',
    '~/assets/css/main.css',
    '~/assets/css/team-filter.css',
    '~/assets/css/fixture-team-name.css',
    '~/assets/css/live-fixtures.css',
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
        { name: 'application-name', content: siteName },
        { property: 'og:title', content: siteTitle },
        { property: 'og:description', content: siteDescription },
        { property: 'og:type', content: 'website' },
        { property: 'og:url', content: siteUrl },
        { property: 'og:image', content: ogImageUrl },
        { property: 'og:image:type', content: 'image/png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { property: 'og:image:alt', content: 'Match Calendar - More Football in Your Everyday.' },
        { property: 'og:site_name', content: siteName },
        { property: 'og:locale', content: 'ja_JP' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:title', content: siteTitle },
        { name: 'twitter:description', content: siteDescription },
        { name: 'twitter:image', content: ogImageUrl },
        { name: 'twitter:image:alt', content: 'Match Calendar - More Football in Your Everyday.' },
        { name: 'theme-color', content: brandColor },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
        { name: 'apple-mobile-web-app-title', content: siteName },
      ],
      link: [
        { rel: 'canonical', href: siteUrl },
        { rel: 'manifest', href: '/manifest.webmanifest' },
        { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
      ],
      script: [
        {
          innerHTML: themeInitScript,
        },
        {
          type: 'application/ld+json',
          innerHTML: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebApplication',
            name: siteName,
            alternateName: 'マッチカレンダー',
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
      name: siteName,
      short_name: siteName,
      description: siteDescription,
      lang: 'ja',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      background_color: brandColor,
      theme_color: brandColor,
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
          src: '/pwa-maskable-512x512.png',
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
