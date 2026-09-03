/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  // Backend de aynı köke tek bir `.env` okur (src/config.py REPO_ROOT/.env) — tek
  // dosya, tek kaynak. Aksi halde VITE_SUPABASE_* değişkenleri burada tanımlansa da
  // Vite varsayılan olarak yalnızca apps/frontend/.env'i okur, sessizce boş kalırdı.
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
        theme_color: '#2563eb',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        ],
      },
      workbox: {
        navigateFallback: 'index.html',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    watch: {
      // Editör geçici dosyaları (…tmpdir/*.tmp) Vite izleyicisini EBUSY ile çökertiyor — yoksay
      ignored: ['**/*.tmp*', '**/.tmpdir/**', '**/.*.tmpdir/**'],
    },
    proxy: {
      // Geliştirmede backend'e ulaşım (yol haritası 2.2)
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
