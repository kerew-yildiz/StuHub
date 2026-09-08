// Geçici: yalnızca Impeccable UI/UX critique oturumu için — canlı dev sunucusuna
// (port 5173 -> 8000, gerçek Supabase) dokunmadan izole bir yerel-mod önizlemesi.
// İnceleme bitince silinecek, commit edilmeyecek.
import baseConfig from './vite.config'

export default {
  ...baseConfig,
  server: {
    ...(baseConfig as { server?: object }).server,
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8010', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8010', changeOrigin: true },
    },
  },
}
