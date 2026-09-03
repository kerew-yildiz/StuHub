import { useEffect, useState } from 'react'

import type { LLMProviderStatus } from '../api/settings'
import { settingsApi } from '../api/settings'

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
    providerName: 'github',
    settingKey: 'github_token',
    label: 'GitHub Token',
    hint: 'github.com/settings/tokens — "models: read" izniyle.',
  },
] as const

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Ayarlar sayfası — ücretsiz LLM sağlayıcı zinciri anahtarları + çalışma alışkanlıkları. */
export function SettingsPage() {
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [currentKeyHints, setCurrentKeyHints] = useState<Record<string, string>>({})
  const [providerStatus, setProviderStatus] = useState<LLMProviderStatus[]>([])
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [dailyGoal, setDailyGoal] = useState('3')

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
      window.setTimeout(() => setSaveState('idle'), 3000)
    } catch {
      setSaveState('error')
      setError('Ayarlar kaydedilemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section className="max-w-xl">
      <h1 className="text-3xl font-semibold">Ayarlar</h1>
      <p className="mt-2 text-stuhub-text-secondary">
        LLM sağlayıcı anahtarlarını ve çalışma alışkanlıklarını buradan yönetebilirsin.
      </p>

      <form onSubmit={handleSave} className="mt-8 space-y-6">
        <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6">
          <h2 className="text-lg font-semibold">Yapay zeka — ücretsiz sağlayıcı zinciri</h2>
          <p className="mt-1 text-sm text-stuhub-text-secondary">
            Geçici çözüm: en az bir anahtar gerekli. Birden fazla anahtar girersen hepsi yedek
            olarak sırayla kullanılır — biri günlük kota sınırına ulaşınca otomatik olarak
            sıradakine geçilir. Anahtarlar yalnızca bu cihazda saklanır; asla loglanmaz veya
            başka bir yere gönderilmez. Not/quiz üretimi sırasında materyal içerikleri yalnızca
            çıkarım için aktif sağlayıcıya gider.
          </p>

          {PROVIDER_FIELDS.map((field, index) => {
            const status = providerStatus.find((p) => p.name === field.providerName)
            return (
              <div key={field.settingKey} className="mt-5">
                <div className="mb-1 flex items-center justify-between">
                  <label htmlFor={field.settingKey} className="block text-sm font-medium">
                    {index + 1}. {field.label}
                  </label>
                  {status?.configured && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        status.active
                          ? 'bg-stuhub-success/10 text-stuhub-success'
                          : 'bg-stuhub-text-secondary/10 text-stuhub-text-secondary'
                      }`}
                    >
                      {status.active ? 'Aktif' : 'Kota doldu — yedekte'}
                    </span>
                  )}
                </div>
                <input
                  id={field.settingKey}
                  type="password"
                  value={apiKeys[field.settingKey] ?? ''}
                  onChange={(e) =>
                    setApiKeys((prev) => ({ ...prev, [field.settingKey]: e.target.value }))
                  }
                  placeholder={
                    loaded ? currentKeyHints[field.settingKey] || 'Anahtar girin…' : 'Yükleniyor…'
                  }
                  autoComplete="off"
                  className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
                />
                <p className="mt-1 text-xs text-stuhub-text-secondary">{field.hint}</p>
              </div>
            )
          })}
        </div>

        <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6">
          <h2 className="text-lg font-semibold">Çalışma alışkanlıkları</h2>
          <p className="mt-1 text-sm text-stuhub-text-secondary">
            Günlük hedef, streak halkasının doluluk ölçüsüdür. Varsayılan 3 etkinlik.
          </p>
          <div className="mt-5">
            <label htmlFor="daily-goal" className="mb-1 block text-sm font-medium">
              Günlük hedef (etkinlik sayısı)
            </label>
            <input
              id="daily-goal"
              type="number"
              min={1}
              value={dailyGoal}
              onChange={(e) => setDailyGoal(e.target.value)}
              className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
            />
          </div>
        </div>

        {error && (
          <p role="alert" className="rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
            {error}
          </p>
        )}
        {saveState === 'saved' && (
          <p role="status" className="rounded-sm bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success">
            Ayarlar kaydedildi.
          </p>
        )}

        <button
          type="submit"
          disabled={saveState === 'saving'}
          className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-60"
        >
          {saveState === 'saving' ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
      </form>
    </section>
  )
}
