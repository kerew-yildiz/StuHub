/// <reference types="vitest/config" />
// Test kampanyası (2026-09-10) için izole Vite yapılandırması — ÜRÜN KODU DEĞİL.
//
// Neden ayrı dosya: kullanıcının kendi uvicorn'u `127.0.0.1:8000`'e bağlı ve Windows'ta
// özgül bağlama (127.0.0.1) jokeri (0.0.0.0) loopback'te EZİYOR. Bu yüzden temel
// `vite.config.ts`'in `127.0.0.1:8000` hedefi, test için başlatılan backend'e değil
// kullanıcının (asılı durumdaki) sürecine gidiyordu. Kampanya backend'i 8010'da koşar.
//
// Kampanya bitince bu dosya silinir.
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const HEDEF = 'http://127.0.0.1:8010'

export default defineConfig({
  envDir: '../../',
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'StuHub',
        short_name: 'StuHub',
        description: 'Yerel AI ders çalışma asistanı',
        lang: 'tr',
        theme_color: '#1c1c1e',
        background_color: '#1c1c1e',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: { navigateFallback: 'index.html' },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5190,
    strictPort: true,
    host: '0.0.0.0',
    watch: {
      ignored: ['**/*.tmp*', '**/.tmpdir/**', '**/.*.tmpdir/**'],
    },
    proxy: {
      '/api': { target: HEDEF, changeOrigin: true },
      '/health': { target: HEDEF, changeOrigin: true },
    },
  },
})
