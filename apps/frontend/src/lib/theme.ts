import { settingsApi } from '../api/settings'

/** Kabul edilen tema degerleri. Sunucu ayari (`settings.theme`) ve localStorage
 * aynasi bu ucluyle sinirlidir; bilinmeyen deger varsayilana duser. */
export const THEME_VALUES = ['dark', 'light', 'system'] as const

export type ThemeValue = (typeof THEME_VALUES)[number]

/** Varsayilan: karanlik tema (bugunku gorunum; attribute/ayar yokken de gecerli). */
export const DEFAULT_THEME: ThemeValue = 'dark'

/** localStorage aynasinin anahtari. index.html'deki ilk-boya script'i AYNI
 * anahtari okur (FOUC yok) — iki yer birlikte degismeli. */
export const THEME_STORAGE_KEY = 'stuhub-tema'

export type ResolvedTheme = 'dark' | 'light'

const LIGHT_QUERY = '(prefers-color-scheme: light)'
/** Tarayıcı çubuğu rengi için yedek değerler — normalde `--stuhub-bg` token'ının
 * çözülmüş değeri kullanılır (tek parlaklık düğmesi: theme.css --stuhub-light-ton).
 * CSS yüklenmemişse (test/ilk an) bu sabitler devreye girer. */
const META_RENK: Record<ResolvedTheme, string> = { dark: '#000000', light: '#ebebeb' }

export function isThemeValue(value: string | undefined): value is ThemeValue {
  return value !== undefined && (THEME_VALUES as readonly string[]).includes(value)
}

/** 'Sistem' secenegi isletim sistemi tercihine cozulur; digerleri kendisi. */
export function resolveTheme(value: ThemeValue, sistemAcik: boolean): ResolvedTheme {
  if (value === 'system') return sistemAcik ? 'light' : 'dark'
  return value
}

/** Son uygulanan ayar — 'system' modunda OS tercihi degisince yeniden cozmek icin. */
let aktifAyar: ThemeValue = DEFAULT_THEME
let dinleyiciKuruldu = false

function sistemDegisiminiIzle(): void {
  if (dinleyiciKuruldu || typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  dinleyiciKuruldu = true
  window.matchMedia(LIGHT_QUERY).addEventListener('change', () => {
    if (aktifAyar === 'system') applyTheme('system')
  })
}

/** Temayi aninda uygular: `html[data-theme]` (CSS kutbu) + localStorage aynasi +
 * `<meta name="theme-color">`. Bilinmeyen/eksik degerde varsayilana doner. */
export function applyTheme(value: string | undefined): void {
  const ayar = isThemeValue(value) ? value : DEFAULT_THEME
  aktifAyar = ayar
  const sistemAcik = typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(LIGHT_QUERY).matches
  const tema = resolveTheme(ayar, sistemAcik)
  document.documentElement.dataset.theme = tema
  // Ilk-boya zemin kuralini devre disi birakir (index.html: `:not(.tema-hazir)`):
  // artik zemin theme.css token'indan gelir → tek parlaklik dugmesi html'i de surer.
  document.documentElement.classList.add('tema-hazir')
  try {
    localStorage.setItem(THEME_STORAGE_KEY, ayar)
  } catch {
    // Ozel/gizli modda localStorage yazilamayabilir — tema yine uygulanir.
  }
  // Zemini token'dan oku: parlaklik tek dugmeden (--stuhub-light-ton) yonetilir,
  // meta da onu izler. CSS yoksa (test) sabit yedek kullanilir.
  const zemin = getComputedStyle(document.documentElement).getPropertyValue('--stuhub-bg').trim()
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', zemin || META_RENK[tema])
  sistemDegisiminiIzle()
}

/** Acilista kayitli temayi uygular. Ilk boyada index.html'in senkron aynasi
 * zaten gecerli oldugu icin hata durumunda mevcut tema KORUNUR (sifirlanmaz). */
export async function applyThemeFromSettings(): Promise<void> {
  try {
    const settings = await settingsApi.list()
    if (isThemeValue(settings.theme)) applyTheme(settings.theme)
  } catch {
    // Sunucu okunamadi: yerel ayna (ilk boya) gecerli kalir.
  }
}
