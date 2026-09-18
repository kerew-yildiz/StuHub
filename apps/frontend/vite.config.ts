/// <reference types="vitest/config" />
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const paket = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as {
  version: string
}

/** Derleme kimliği (sürüm + kısa commit). Docker build'inde `.git` kopyalanmaz —
 * orada CI'ın geçtiği BUILD_SHA build-arg'ı okunur (Dockerfile), yerelde git
 * çalışır. Hiçbiri yoksa 'bilinmiyor' (yanlış bilgi vermektense görünür boşluk). */
function derlemeCommiti(): string {
  const disaridan = process.env.BUILD_SHA || process.env.GITHUB_SHA || ''
  if (disaridan) return disaridan.slice(0, 7)
  try {
    return execFileSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8' }).trim()
  } catch {
    return 'bilinmiyor'
  }
}

const DERLEME_COMMIT = derlemeCommiti()
const DERLEME_KIMLIGI = `${paket.version}+${DERLEME_COMMIT}`

/** `dist/version.json`: "yayında hangi sürüm var?" sorusunun sunucudan
 * doğrulanabilir cevabı (`curl /version.json`) — hotfix takibi ve PWA
 * güncelleme doğrulaması bunun üzerinden yapılır. Backend bu dosyayı da
 * no-store ile servis eder (main.py `static_cache_headers`). */
function surumDosyasi(): Plugin {
  return {
    name: 'stuhub-surum-dosyasi',
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'version.json',
        source: `${JSON.stringify(
          {
            version: paket.version,
            commit: DERLEME_COMMIT,
            build: DERLEME_KIMLIGI,
            builtAt: new Date().toISOString(),
          },
          null,
          2,
        )}\n`,
      })
    },
  }
}

export default defineConfig({
  // Derleme kimliği tarayıcıya gömülür (src/lib/pwa-update.ts pencereye yazar):
  // sayfanın hangi build'i çalıştırdığı konsoldan/otomasyondan okunabilir olsun.
  define: { __STUHUB_BUILD__: JSON.stringify(DERLEME_KIMLIGI) },
  // Backend de aynı köke tek bir `.env` okur (src/config.py REPO_ROOT/.env) — tek
  // dosya, tek kaynak. Aksi halde VITE_SUPABASE_* değişkenleri burada tanımlansa da
  // Vite varsayılan olarak yalnızca apps/frontend/.env'i okur, sessizce boş kalırdı.
  envDir: '../../',
  plugins: [
    react(),
    tailwindcss(),
    surumDosyasi(),
    VitePWA({
      registerType: 'autoUpdate',
      // Kayıt istemcide kendi elimizde (src/lib/pwa-update.ts): plugin'in
      // enjekte ettiği/virtual modül kaydı yeni SW aktive olur olmaz koşulsuz
      // sayfayı yeniliyor ve "form doluyken sessiz yenileme yapma" kuralını
      // deliyordu. `null`: hiçbir kayıt betiği enjekte edilmez.
      injectRegister: null,
      manifest: {
        name: 'StuHub',
        short_name: 'StuHub',
        description: 'Yerel AI ders çalışma asistanı',
        lang: 'tr',
        theme_color: '#000000',
        background_color: '#000000',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: 'brand/favicon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: 'brand/favicon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: 'brand/apple-touch-icon.png', sizes: '180x180', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        // `navigateFallback` AÇIKÇA null: plugin varsayılanı "index.html"
        // (`defaultWorkbox`), generateSW da NavigationRoute'u runtimeCaching
        // rotalarından ÖNCE kaydediyor. Önbellek-önce kabuk rotası NetworkFirst'ü
        // gölgeler ve çevrimiçi kullanıcıya precache'teki eski index.html'i servis
        // eder — raporlanan "eski sürüm takılı kaldı" davranışının 2. kök nedeni.
        // Yerine tek rota: document istekleri ağdan (4 sn zaman aşımı), ağ yoksa
        // precache'teki kabuğa düşer (PrecacheFallbackPlugin).
        navigateFallback: null,
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.mode === 'navigate',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'stuhub-sayfa-kabugu',
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 8 },
              precacheFallback: { fallbackURL: 'index.html' },
            },
          },
        ],
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
    // Yalnızca uygulama kaynağındaki testler koşar (varsayılan include deseni
    // node_modules içindeki paket testlerini de topluyordu).
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules/**', 'dist/**'],
  },
})
