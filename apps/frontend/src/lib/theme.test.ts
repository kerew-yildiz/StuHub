import { readFileSync } from 'node:fs'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { settingsApi } from '../api/settings'
import { applyTheme, applyThemeFromSettings, THEME_STORAGE_KEY } from './theme'

vi.mock('../api/settings', () => ({
  settingsApi: { list: vi.fn(), set: vi.fn() },
}))

/** `prefers-color-scheme` kontrolü: OS tercihi testler arasında değiştirilebilir
 * ve dinleyiciler elle tetiklenir (gerçek medya sorgusu jsdom'da yok). */
let sistemAcik = false
const dinleyiciler: Array<(e: MediaQueryListEvent) => void> = []

window.matchMedia = ((sorgu: string) => ({
  matches: sistemAcik,
  media: sorgu,
  onchange: null,
  addEventListener: (_tur: string, cb: (e: MediaQueryListEvent) => void) => dinleyiciler.push(cb),
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
})) as unknown as typeof window.matchMedia

function osTercihiDegistir(acik: boolean): void {
  sistemAcik = acik
  dinleyiciler.forEach((cb) => cb({ matches: acik } as unknown as MediaQueryListEvent))
}

function metaTemaRengi(): string | null {
  return document.querySelector('meta[name="theme-color"]')?.getAttribute('content') ?? null
}

beforeEach(() => {
  localStorage.clear()
  document.head.innerHTML = '<meta name="theme-color" content="#000000">'
  sistemAcik = false
})

describe('tema uygulama', () => {
  it('acik tema attribute + yerel ayna + tarayici rengini gunceller', () => {
    applyTheme('light')

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    // Ilk-boya zemin kuralini devre disi birakan sinif eklendi mi?
    expect(document.documentElement.classList.contains('tema-hazir')).toBe(true)
    // CSS yuklu degilse (jsdom) yedek deger: acik tema dim tonu (#ebebeb).
    expect(metaTemaRengi()).toBe('#ebebeb')
  })

  it('karanlik tema varsayilan kutba doner', () => {
    applyTheme('light')
    applyTheme('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(metaTemaRengi()).toBe('#000000')
  })

  it('bilinmeyen ayar degeri varsayilana duser', () => {
    applyTheme('mavi')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('sistem modu isletim sistemi tercihini izler ve degisimde guncellenir', () => {
    applyTheme('system')
    expect(document.documentElement.dataset.theme).toBe('dark')

    osTercihiDegistir(true)
    expect(document.documentElement.dataset.theme).toBe('light')

    osTercihiDegistir(false)
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('sistem disi secimde OS tercihi degisimi temayi bozmaz', () => {
    applyTheme('light')
    osTercihiDegistir(false)

    expect(document.documentElement.dataset.theme).toBe('light')
  })
})

describe('sunucu ayari', () => {
  it('kayitli tema ayarini uygular', async () => {
    vi.mocked(settingsApi.list).mockResolvedValue({ theme: 'light' })

    await applyThemeFromSettings()

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('tanimsiz ayarda ilk boya aynasini bozmaz', async () => {
    applyTheme('light')
    vi.mocked(settingsApi.list).mockResolvedValue({})

    await applyThemeFromSettings()

    expect(document.documentElement.dataset.theme).toBe('light')
  })

  /** Regresyon (2026-09-17): açılışta başlayan `/api/settings` isteği, kullanıcı ayarlar
   * ekranından tema seçtikten SONRA dönerse eski değerle seçimi eziyordu. Statik içe
   * aktarma burada yetmez: işaret MODÜL seviyesi durumda tutulur ve bu testin onu
   * kirletmeden gözleyebilmesi için taze modül örneği gerekir (resetModules + import). */
  it('kullanici sectikten sonra donen acilis yaniti secimi ezmez', async () => {
    vi.resetModules()
    const tema = await import('./theme')
    let coz: (v: Record<string, string>) => void = () => undefined
    vi.mocked(settingsApi.list).mockImplementation(
      () => new Promise<Record<string, string>>((resolve) => { coz = resolve }),
    )

    const bekleyen = tema.applyThemeFromSettings()
    tema.applyTheme('light')
    tema.markThemeChosen()
    coz({ theme: 'dark' })
    await bekleyen

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })
})

describe('ilk boya sozlesmesi (index.html)', () => {
  it('senkron script ayni anahtari okuyup data-theme yazar', () => {
    // jsdom'da import.meta.url http semasindadir; dosya vitest kokunde (apps/frontend).
    const html = readFileSync('index.html', 'utf8')

    expect(html).toContain(`'${THEME_STORAGE_KEY}'`)
    expect(html).toMatch(/dataset\.theme\s*=/)
    // Ilk boya zemini tema attribute'una gore: karanlik #000, acik #ebebeb (dim).
    // `:not(.tema-hazir)` — uygulama acilinca kural devre disi kalir, zemin token'a gecer.
    expect(html).toContain('html[data-theme="light"]:not(.tema-hazir){background:#ebebeb}')
  })
})
