import { settingsApi } from '../api/settings'

/** Kabul edilen arkaplan degerleri.
 * Yeni arkaplan secenegi eklerken: buraya degeri ekle + styles/personalization.css'e
 * ayni katman yapisiyla html[data-stuhub-bg='<deger>'] body kuralini ekle. */
export const BACKGROUND_VALUES = ['calisma-masasi', 'zirve'] as const

export type BackgroundValue = (typeof BACKGROUND_VALUES)[number]

/** Attribute yokken theme.css'teki varsayilan arkaplan gecerli olur. */
export const DEFAULT_BACKGROUND: BackgroundValue = 'calisma-masasi'

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
    applyBackground(settings.background)
  } catch {
    applyBackground(undefined)
  }
}
