import { settingsApi } from '../api/settings'

/** Kabul edilen arkaplan degerleri.
 * Yeni arkaplan secenegi eklerken: buraya degeri ekle + styles/personalization.css'e
 * ayni katman yapisiyla html[data-stuhub-bg='<deger>'] body kuralini ekle. */
export const BACKGROUND_VALUES = [
  'calisma-masasi',
  'zirve',
  // Arkaplan katalogu genisletmesi (planlar/ARKAPLAN-PROMPTLARI.md sirasi).
  'uyanis',
  'merdiven',
  'yolculuk',
  'ufuk',
  'yuk-tasima',
  'sinav-sabahi',
  'kale',
  'yelken',
] as const

export type BackgroundValue = (typeof BACKGROUND_VALUES)[number]

/** Attribute yokken theme.css'teki varsayilan arkaplan gecerli olur. */
export const DEFAULT_BACKGROUND: BackgroundValue = 'calisma-masasi'

/** Kullanıcı bu oturumda arkaplanı elle seçti mi (bkz. `markBackgroundChosen`). */
let kullaniciSecti = false

/** Ayarlar sayfası arkaplan seçiminde çağrılır: açılışta başlayan `/api/settings`
 * isteği seçimden sonra dönerse eski değerle seçimi ezmesin (tema ile aynı yarış). */
export function markBackgroundChosen(): void {
  kullaniciSecti = true
}

export function isBackgroundValue(value: string | undefined): value is BackgroundValue {
  return value !== undefined && (BACKGROUND_VALUES as readonly string[]).includes(value)
}

/** Arkaplani aninda uygular; bilinmeyen/eksik degerde varsayilana doner (attribute silinir). */
export function applyBackground(value: string | undefined): void {
  if (isBackgroundValue(value)) {
    document.documentElement.dataset.stuhubBg = value
  } else {
    delete document.documentElement.dataset.stuhubBg
  }
}

/** Acilista kayitli arkaplani uygular — cagiran bloklamaz, hata yutulur (varsayilan kalir). */
export async function applyBackgroundFromSettings(): Promise<void> {
  try {
    const settings = await settingsApi.list()
    if (kullaniciSecti) return  // kullanıcı yanıt dönerken seçti — üzerine yazma
    applyBackground(settings.background)
  } catch {
    if (!kullaniciSecti) applyBackground(undefined)
  }
}
