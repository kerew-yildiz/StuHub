import { useEffect, useRef, useState } from 'react'

import { settingsApi } from '../api/settings'
import type { BackgroundValue } from '../lib/personalization'
import { applyBackground, DEFAULT_BACKGROUND, isBackgroundValue, markBackgroundChosen } from '../lib/personalization'
import type { ThemeValue } from '../lib/theme'
import { applyTheme, DEFAULT_THEME, isThemeValue, markThemeChosen } from '../lib/theme'
import { useAuthStore } from '../stores/authStore'

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Sekme/panel ARIA kimliği için kategori adını slug'a çevirir: 'Öğrenme tercihleri' → 'ogrenme-tercihleri'. */
const SLUG_CHARS: Record<string, string> = { ç: 'c', ğ: 'g', ı: 'i', ö: 'o', ş: 's', ü: 'u' }
const slug = (label: string) => label.toLowerCase().replace(/[çğıöşü]/g, (c) => SLUG_CHARS[c]).replace(/\s+/g, '-')

/** Arkaplan katalogu — Turkce gorunur ad + gorsel onizleme.
 * Sira: once mevcut arkaplanlar, sonra ARKAPLAN-PROMPTLARI.md etiket sirasi. */
const BACKGROUND_OPTIONS: ReadonlyArray<{ value: BackgroundValue; src: string; label: string }> = [
  { value: 'calisma-masasi', src: '/bg/calisma-masasi.png', label: 'Çalışma Masası' },
  { value: 'zirve', src: '/bg/zirve.jpg', label: 'Zirve' },
  { value: 'uyanis', src: '/bg/uyanis.jpg', label: 'Uyanış' },
  { value: 'merdiven', src: '/bg/merdiven.jpg', label: 'Merdiven' },
  { value: 'yolculuk', src: '/bg/yolculuk.jpg', label: 'Yolculuk' },
  { value: 'ufuk', src: '/bg/ufuk.jpg', label: 'Ufuk' },
  { value: 'yuk-tasima', src: '/bg/yuk-tasima.jpg', label: 'Yük Taşıma' },
  { value: 'sinav-sabahi', src: '/bg/sinav-sabahi.jpg', label: 'Sınav Sabahı' },
  { value: 'kale', src: '/bg/kale.jpg', label: 'Kitap Kalesi' },
  { value: 'yelken', src: '/bg/yelken.jpg', label: 'Yelken' },
]

/** Tema katalogu — Karanlik varsayilan; "ters kutup" ayni tasarimin acik hali. */
const THEME_OPTIONS: ReadonlyArray<{ value: ThemeValue; label: string; aciklama: string }> = [
  { value: 'dark', label: 'Karanlık', aciklama: 'Varsayılan' },
  { value: 'light', label: 'Açık', aciklama: 'Ters kutup' },
  { value: 'system', label: 'Sistem', aciklama: 'İşletim sistemi tercihi' },
]

/** Kisillestirme bolumu — tema secici (Karanlik / Acik / Sistem).
 * Secim aninda uygulanir (html[data-theme]) ve mevcut ayar akisiyla kalici olur;
 * ilk boyada index.html'deki senkron ayna devreye girer (FOUC yok). */
function ThemeSection({
  value,
  onChange,
}: {
  value: ThemeValue
  onChange: (value: ThemeValue) => void
}) {
  return (
    <div className="glass-panel p-6">
      <h2 className="text-lg font-semibold">Tema</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Karanlık varsayılandır; açık tema aynı tasarımın ters çevrilmiş kutbudur (cam,
        yuvarlaklık ve ölçüler değişmez).
      </p>
      <div role="radiogroup" aria-label="Tema" className="mt-5 flex flex-wrap gap-3">
        {THEME_OPTIONS.map((option) => {
          const selected = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(option.value)}
              className={`flex min-w-[132px] flex-col gap-0.5 rounded-control border-2 px-4 py-3 text-left transition-all duration-[var(--duration-state)] ${
                selected
                  ? 'border-stuhub-accent opacity-100 shadow-[0_0_0_3px_var(--stuhub-accent-glass)]'
                  : 'border-stuhub-border opacity-75 hover:opacity-100'
              }`}
            >
              <span className="text-sm font-medium">{option.label}</span>
              <span className="text-xs text-stuhub-text-muted">{option.aciklama}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Kisillestirme bolumu — arkaplan secici (gorsel onizleme katalogu). */
function BackgroundSection({
  value,
  onChange,
}: {
  value: BackgroundValue
  onChange: (value: BackgroundValue) => void
}) {
  return (
    <div className="glass-panel p-6">
      <h2 className="text-lg font-semibold">Arkaplanlar</h2>
      <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3">
        {BACKGROUND_OPTIONS.map((option) => {
          const selected = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-label={option.label}
              aria-pressed={selected}
              title={option.label}
              className={`relative aspect-video overflow-hidden rounded-control border-2 transition-all duration-[var(--duration-state)] ${
                selected
                  ? 'border-stuhub-accent opacity-100 shadow-[0_0_0_3px_var(--stuhub-accent-glass)]'
                  : 'border-stuhub-border opacity-75 hover:opacity-100'
              }`}
            >
              <img src={option.src} alt="" draggable={false} className="h-full w-full object-cover" />
              <span
                aria-hidden="true"
                className="absolute inset-x-0 bottom-0 truncate bg-stuhub-caption-bg px-1.5 py-1 text-center text-[10px] font-medium leading-none text-stuhub-text-secondary"
              >
                {option.label}
              </span>
              {selected && (
                <span
                  aria-hidden="true"
                  className="absolute right-1.5 top-1.5 inline-flex h-5 w-5 items-center justify-center rounded-pill bg-stuhub-accent text-stuhub-on-accent"
                >
                  <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 12.5l5.2 5.2L20 7" />
                  </svg>
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** Ayarlar sayfası — hesap, çalışma alışkanlıkları ve kişiselleştirme. */
/** Hesap bölümü — gerçek kullanıcı verisi (§102: placeholder yasak). */
function AccountSection() {
  const user = useAuthStore((s) => s.user)
  const saasMode = useAuthStore((s) => s.saasMode)
  const metadata = user?.user_metadata as Record<string, unknown> | undefined
  const nameCandidate = metadata?.full_name ?? metadata?.name
  const displayName = typeof nameCandidate === 'string' && nameCandidate.trim()
    ? nameCandidate.trim()
    : user?.email?.split('@')[0] ?? 'Öğrenci'
  const email = user?.email ?? 'Yerel kullanıcı'
  const tier = saasMode ? 'FREE' : 'PRO'

  const initials = displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toLocaleUpperCase('tr-TR'))
    .join('')

  return (
    <div className="glass-panel p-6">
      <p className="eyebrow">Hesap</p>
      <h2 className="mt-2 text-xl font-semibold">Profil bilgileri</h2>
      <div className="mt-5 flex items-center gap-4">
        <span className="avatar avatar--large" aria-hidden="true">{initials || '?'}</span>
        <div className="min-w-0">
          <p className="truncate font-semibold">{displayName}</p>
          <p className="truncate text-sm text-stuhub-text-secondary">{email}</p>
        </div>
        <span className="glass-panel-subtle rounded-pill ml-auto px-3 py-1 text-xs font-semibold">{tier}</span>
      </div>
      {saasMode && (
        <p className="mt-5 text-sm text-stuhub-text-secondary">
          Planını yükseltmek için <a href="/paywall" className="text-stuhub-accent underline underline-offset-2">yükseltme sayfasına</a> göz at.
        </p>
      )}
    </div>
  )
}

export function SettingsPage() {
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState('')
  const [dailyGoal, setDailyGoal] = useState('3')
  const [background, setBackground] = useState<BackgroundValue>(DEFAULT_BACKGROUND)
  const [theme, setTheme] = useState<ThemeValue>(DEFAULT_THEME)
  const [category, setCategory] = useState('AI tercihleri')
  // "Kaydedildi" göstergesinin timeout'u — unmount'ta temizlenir (önceden ham
  // setTimeout'tu; hızlı sayfa geçişinde unmount sonrası setState uyarısı üretirdi).
  const savedTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (savedTimerRef.current !== null) window.clearTimeout(savedTimerRef.current)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    settingsApi
      .list()
      .then((settings) => {
        if (cancelled) return
        if (settings.daily_goal) setDailyGoal(settings.daily_goal)
        if (isBackgroundValue(settings.background)) setBackground(settings.background)
        if (isThemeValue(settings.theme)) setTheme(settings.theme)
      })
      .catch(() => {
        if (!cancelled) setError('Ayarlar yüklenemedi. Lütfen tekrar deneyin.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleBackgroundSelect = (value: BackgroundValue) => {
    setBackground(value)
    markBackgroundChosen()
    applyBackground(value)
    // Ayar kaydi kritik degil — hata sessizce yutulur (attribute zaten uygulandi).
    settingsApi.set('background', value).catch(() => undefined)
  }

  const handleThemeSelect = (value: ThemeValue) => {
    setTheme(value)
    markThemeChosen()
    applyTheme(value)
    // Ayar kaydi kritik degil — hata sessizce yutulur (tema zaten uygulandi).
    settingsApi.set('theme', value).catch(() => undefined)
  }

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaveState('saving')
    setError('')
    try {
      const goal = Number.parseInt(dailyGoal, 10)
      await settingsApi.set('daily_goal', String(Number.isNaN(goal) || goal <= 0 ? 3 : goal))
      setSaveState('saved')
      if (savedTimerRef.current !== null) window.clearTimeout(savedTimerRef.current)
      savedTimerRef.current = window.setTimeout(() => setSaveState('idle'), 3000)
    } catch {
      setSaveState('error')
      setError('Ayarlar kaydedilemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section className="page-shell">
      <header className="page-header">
        <div>
          <h1 className="page-title">Ayarlar</h1>
          <p className="page-subtitle">Çalışma alışkanlıkları ve kişiselleştirme.</p>
        </div>
      </header>

      <div className="settings-layout">
        <nav className="glass-panel-subtle settings-nav" role="tablist" aria-label="Ayar kategorileri">
          {['Hesap','Bildirimler','Veri','Öğrenme tercihleri','AI tercihleri','Kişiselleştirme','Kısayollar'].map((item) => (
            <button key={item} type="button" role="tab" id={`sekme-${slug(item)}`} aria-selected={category === item} aria-controls={`panel-${slug(item)}`} tabIndex={category === item ? 0 : -1} onClick={() => { setCategory(item); setError(''); setSaveState('idle') }} className={`settings-nav__item ${category === item ? 'settings-nav__item--active' : ''}`}>{item}</button>
          ))}
        </nav>

        <div className="settings-content" role="tabpanel" id={`panel-${slug(category)}`} aria-labelledby={`sekme-${slug(category)}`}>
          {(category === 'AI tercihleri') && (
            <form onSubmit={handleSave} className="settings-content">
              <div className="glass-panel p-6">
                <h2 className="text-lg font-semibold">Çalışma hedefi</h2>
                <p className="mt-1 text-sm text-stuhub-text-secondary">Günlük hedef, streak halkasının doluluk ölçüsüdür.</p>
                <div className="mt-5">
                  <label htmlFor="daily-goal" className="mb-1 block text-sm font-medium">Günlük hedef (etkinlik sayısı)</label>
                  <input id="daily-goal" type="number" min={1} value={dailyGoal} onChange={(e) => setDailyGoal(e.target.value)} className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none focus:border-stuhub-accent" />
                </div>
              </div>

              {error && <p role="alert" className="rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">{error}</p>}
              {saveState === 'saved' && <p role="status" className="rounded-control bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success">Ayarlar kaydedildi.</p>}
              <button type="submit" disabled={saveState === 'saving'} className="btn-primary">{saveState === 'saving' ? 'Kaydediliyor…' : 'Kaydet'}</button>
            </form>
          )}

          {category === 'Hesap' && <AccountSection />}

          {category === 'Bildirimler' && (
            <div className="glass-panel p-6">
              <h2 className="text-lg font-semibold">Bildirimler</h2>
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                StuHub bildirimleri uygulama içi tepkisel bildirimlerdir (üretim bitti, hata
                oluştu, kota doldu). E-posta/push bildirimi bu sürümde yoktur — burada
                görebileceğin tek bildirim kaynağı üst çubuktaki zil ikonudur.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-stuhub-text-secondary">
                <li className="glass-panel-subtle rounded-control px-4 py-3">Not / kart / quiz üretimi bittiğinde zil ikonunda rozet belirir.</li>
                <li className="glass-panel-subtle rounded-control px-4 py-3">Hatalı istekler sağ altta kırmızı toast olarak gösterilir; kapatana kadar ekranda kalır.</li>
              </ul>
            </div>
          )}

          {category === 'Veri' && (
            <div className="glass-panel p-6">
              <h2 className="text-lg font-semibold">Veri</h2>
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Notların, kartların ve çalışma geçmişin hesabına bağlıdır. Dışa aktarma
                işlemleri ilgili çalışma alanının içindedir (not için MD/PDF). Hesap silme
                talebi için destek ile iletişime geç.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-stuhub-text-secondary">
                <li className="glass-panel-subtle rounded-control px-4 py-3">Not dışa aktarma: Not görünümü → “PDF İndir” ya da “MD İndir”.</li>
                <li className="glass-panel-subtle rounded-control px-4 py-3">Çalışma süreleri haftalık grafikte toplanır; ayrı bir dışa aktarımı yoktur.</li>
              </ul>
            </div>
          )}

          {category === 'Öğrenme tercihleri' && (
            <div className="glass-panel p-6">
              <h2 className="text-lg font-semibold">Öğrenme tercihleri</h2>
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Günlük hedef ve tekrar akışı buradan yönetilir. Günlük hedef kaydedildiğinde
                streak halkası buna göre dolar.
              </p>
              <div className="mt-5">
                <label htmlFor="daily-goal-learn" className="mb-1 block text-sm font-medium">Günlük hedef (etkinlik sayısı)</label>
                <input
                  id="daily-goal-learn"
                  type="number"
                  min={1}
                  value={dailyGoal}
                  onChange={(e) => setDailyGoal(e.target.value)}
                  className="w-full max-w-xs rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none focus:border-stuhub-accent"
                />
                <button
                  type="button"
                  className="btn-primary mt-4"
                  disabled={saveState === 'saving'}
                  onClick={(e) => void handleSave(e as unknown as React.FormEvent)}
                >
                  {saveState === 'saving' ? 'Kaydediliyor…' : 'Kaydet'}
                </button>
                {saveState === 'saved' && <p role="status" className="mt-3 rounded-control bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success">Ayarlar kaydedildi.</p>}
                {error && <p role="alert" className="mt-3 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">{error}</p>}
              </div>
            </div>
          )}

          {category === 'Kişiselleştirme' && (
            <>
              <ThemeSection value={theme} onChange={handleThemeSelect} />
              <BackgroundSection value={background} onChange={handleBackgroundSelect} />
            </>
          )}

          {category === 'Kısayollar' && (
            <div className="glass-panel p-6">
              <h2 className="text-lg font-semibold">Klavye kısayolları</h2>
              <div className="mt-4 list-stack">
                <div className="glass-panel-subtle list-card"><span>Komut paleti / arama</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">Ctrl K</kbd></div>
                <div className="glass-panel-subtle list-card"><span>Yardım turu</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">?</kbd></div>
                <div className="glass-panel-subtle list-card"><span>Flashcard çevir</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">Space</kbd></div>
                <div className="glass-panel-subtle list-card"><span>Flashcard doğru / yanlış</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">→ / ←</kbd></div>
                <div className="glass-panel-subtle list-card"><span>Quiz feed gezinme</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">↑ / ↓</kbd></div>
                <div className="glass-panel-subtle list-card"><span>Ders sekme grupları</span><kbd className="glass-panel-subtle rounded-chip px-2 py-1 text-xs">1–4</kbd></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
