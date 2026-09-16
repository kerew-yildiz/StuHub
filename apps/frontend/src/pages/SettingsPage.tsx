import { useEffect, useRef, useState } from 'react'

import type { LLMProviderStatus } from '../api/settings'
import { settingsApi } from '../api/settings'
import type { BackgroundValue } from '../lib/personalization'
import { applyBackground, DEFAULT_BACKGROUND, isBackgroundValue } from '../lib/personalization'
import { useAuthStore } from '../stores/authStore'

/** Ücretsiz LLM sağlayıcı zinciri — geçici çözüm (Kerem kararı, 2026-09-02).
 * Sıra yetenek sırasıdır: biri kota sınırına ulaşınca otomatik sıradakine geçilir. */
const PROVIDER_FIELDS = [
  {
    providerName: 'gemini',
    settingKey: 'google_api_key',
    label: 'Google Gemini API anahtarı',
    hint: 'aistudio.google.com/apikey — en geniş kota, önerilen.',
  },
  {
    providerName: 'openrouter',
    settingKey: 'openrouter_api_key',
    label: 'OpenRouter API anahtarı',
    hint: 'openrouter.ai/keys — Nemotron 3 Ultra 550B ücretsiz varyantı.',
  },
  {
    providerName: 'groq',
    settingKey: 'groq_api_key',
    label: 'Groq API anahtarı',
    hint: 'console.groq.com/keys — en yüksek hacim.',
  },
  {
    providerName: 'cerebras',
    settingKey: 'cerebras_api_key',
    label: 'Cerebras API anahtarı',
    hint: 'cloud.cerebras.ai/platform/keys — geçici test (2026-09-05).',
  },
  {
    providerName: 'github',
    settingKey: 'github_token',
    label: 'GitHub Token',
    hint: 'github.com/settings/tokens — "models: read" izniyle.',
  },
] as const

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Sekme/panel ARIA kimliği için kategori adını slug'a çevirir: 'Öğrenme tercihleri' → 'ogrenme-tercihleri'. */
const SLUG_CHARS: Record<string, string> = { ç: 'c', ğ: 'g', ı: 'i', ö: 'o', ş: 's', ü: 'u' }
const slug = (label: string) => label.toLowerCase().replace(/[çğıöşü]/g, (c) => SLUG_CHARS[c]).replace(/\s+/g, '-')

/** Arkaplan katalogu — kartlarda gorunur metin yok; eslesme yalnizca gorsel onizleme. */
const BACKGROUND_OPTIONS: ReadonlyArray<{ value: BackgroundValue; src: string }> = [
  { value: 'calisma-masasi', src: '/bg/calisma-masasi.png' },
  { value: 'zirve', src: '/bg/zirve.jpg' },
]

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
        {BACKGROUND_OPTIONS.map((option, index) => {
          const selected = option.value === value
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              aria-label={`Arkaplan ${index + 1}`}
              aria-pressed={selected}
              title={`Arkaplan ${index + 1}`}
              className={`relative aspect-video overflow-hidden rounded-control border-2 transition-all duration-200 ${
                selected
                  ? 'border-stuhub-accent opacity-100 shadow-[0_0_0_3px_var(--stuhub-accent-glass)]'
                  : 'border-stuhub-border opacity-75 hover:opacity-100'
              }`}
            >
              <img src={option.src} alt="" draggable={false} className="h-full w-full object-cover" />
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

/** Ayarlar sayfası — ücretsiz LLM sağlayıcı zinciri anahtarları + çalışma alışkanlıkları. */
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
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [currentKeyHints, setCurrentKeyHints] = useState<Record<string, string>>({})
  const [providerStatus, setProviderStatus] = useState<LLMProviderStatus[]>([])
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [dailyGoal, setDailyGoal] = useState('3')
  const [background, setBackground] = useState<BackgroundValue>(DEFAULT_BACKGROUND)
  const [category, setCategory] = useState('AI tercihleri')
  // "Kaydedildi" göstergesinin timeout'u — unmount'ta temizlenir (önceden ham
  // setTimeout'tu; hızlı sayfa geçişinde unmount sonrası setState uyarısı üretirdi).
  const savedTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (savedTimerRef.current !== null) window.clearTimeout(savedTimerRef.current)
    }
  }, [])

  const refreshStatus = () => {
    settingsApi.llmStatus().then(setProviderStatus).catch(() => undefined)
  }

  useEffect(() => {
    let cancelled = false
    settingsApi
      .list()
      .then((settings) => {
        if (cancelled) return
        if (settings.daily_goal) setDailyGoal(settings.daily_goal)
        if (isBackgroundValue(settings.background)) setBackground(settings.background)
        const hints: Record<string, string> = {}
        for (const field of PROVIDER_FIELDS) {
          if (settings[field.settingKey]) {
            hints[field.settingKey] = `${settings[field.settingKey]} (güncel anahtar)`
          }
        }
        setCurrentKeyHints(hints)
        setLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setError('Ayarlar yüklenemedi. Lütfen tekrar deneyin.')
      })
    refreshStatus()
    return () => {
      cancelled = true
    }
  }, [])

  const handleBackgroundSelect = (value: BackgroundValue) => {
    setBackground(value)
    applyBackground(value)
    // Ayar kaydi kritik degil — hata sessizce yutulur (attribute zaten uygulandi).
    settingsApi.set('background', value).catch(() => undefined)
  }

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaveState('saving')
    setError('')
    try {
      for (const field of PROVIDER_FIELDS) {
        const value = apiKeys[field.settingKey]?.trim()
        if (value) {
          await settingsApi.set(field.settingKey, value)
        }
      }
      const goal = Number.parseInt(dailyGoal, 10)
      await settingsApi.set('daily_goal', String(Number.isNaN(goal) || goal <= 0 ? 3 : goal))
      setSaveState('saved')
      setApiKeys({})
      refreshStatus()
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
          <p className="page-subtitle">LLM sağlayıcıları ve çalışma alışkanlıkları.</p>
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
                <h2 className="text-lg font-semibold">Yapay zeka — ücretsiz sağlayıcı zinciri</h2>
                <p className="mt-1 text-sm text-stuhub-text-secondary">
                  Birden fazla anahtar girersen sağlayıcılar sırayla yedek olarak kullanılabilir.
                  Anahtar değerleri arayüzde maskeli tutulur.
                </p>
                {PROVIDER_FIELDS.map((field, index) => {
                  const status = providerStatus.find((p) => p.name === field.providerName)
                  return (
                    <div key={field.settingKey} className="mt-5">
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <label htmlFor={field.settingKey} className="block text-sm font-medium">{index + 1}. {field.label}</label>
                        {status?.configured && (
                          <span className="glass-panel-subtle rounded-pill px-2.5 py-1 text-xs text-stuhub-text-secondary">
                            {status.cooldown_until
                              ? `Kota doldu — ${new Date(status.cooldown_until).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`
                              : status.active ? 'Aktif' : 'Yedekte'}
                          </span>
                        )}
                      </div>
                      <input id={field.settingKey} type="password" value={apiKeys[field.settingKey] ?? ''} onChange={(e) => setApiKeys((prev) => ({ ...prev, [field.settingKey]: e.target.value }))} placeholder={loaded ? currentKeyHints[field.settingKey] || 'Anahtar girin…' : 'Yükleniyor…'} autoComplete="off" className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none focus:border-stuhub-accent" />
                      <p className="mt-1 text-xs text-stuhub-text-muted">{field.hint}</p>
                    </div>
                  )
                })}
              </div>

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
                <li className="glass-panel-subtle rounded-control px-4 py-3">Kota dolan sağlayıcılar AI tercihleri sekmesinde işaretlenir.</li>
              </ul>
            </div>
          )}

          {category === 'Veri' && (
            <div className="glass-panel p-6">
              <h2 className="text-lg font-semibold">Veri</h2>
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Notların, kartların ve çalışma geçmişin hesabına bağlıdır. Dışa aktarma
                işlemleri ilgili çalışma alanının içindedir (not için MD/PDF, kartlar için
                Anki/CSV). Hesap silme talebi için destek ile iletişime geç.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-stuhub-text-secondary">
                <li className="glass-panel-subtle rounded-control px-4 py-3">Not dışa aktarma: Not görünümü → “PDF İndir” ya da “MD İndir”.</li>
                <li className="glass-panel-subtle rounded-control px-4 py-3">Kart dışa aktarma: Kartlar görünümü → “Anki (.apkg)” ya da “CSV”.</li>
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
            <BackgroundSection value={background} onChange={handleBackgroundSelect} />
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
