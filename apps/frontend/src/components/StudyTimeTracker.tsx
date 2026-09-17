import { useStudyTimeTracker } from '../hooks/useStudyTimeTracker'

/**
 * Otomatik çalışma süresi takibini DOM'suz (null render) bir bileşene bağlar.
 *
 * Hook doğrudan `App` gövdesinde ÇAĞRILMAZ: App'te erken `return` dalları
 * (yükleme iskeleti, giriş ekranı) var ve hook listesi App gövdesine bağlı kalırsa
 * hook'un kendi hook sayısı değiştiğinde (HMR ile canlı güncelleme) React
 * "Rendered more hooks than during the previous render" ile çöker — canlıda
 * yaşandı (2026-09-17). Bileşen sınırında Fast Refresh yalnız bu bileşeni yeniden
 * mount eder; App'in hook listesi her koşulda sabit kalır.
 *
 * Ölçüm chapter görünümünde heartbeat, diğer sayfalarda 5 dk'lık global blok olarak
 * yazılır (bkz. `useStudyTimeTracker`). Oturumlu kabukta render edilir — giriş
 * ekranında/yükleme sırasında ölçülecek aktif çalışma yoktur.
 */
export function StudyTimeTracker() {
  useStudyTimeTracker()
  return null
}
