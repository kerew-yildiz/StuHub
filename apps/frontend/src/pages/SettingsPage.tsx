import { useEffect, useState } from 'react'

import type { LLMProviderStatus } from '../api/settings'
import { settingsApi } from '../api/settings'

/** Ücretsiz LLM sağlayıcı zinciri — geçici çözüm (Kerem kararı, 2026-09-02).
 * Sıra yetenek sırasıdır: biri kota sınırına ulaşınca otomatik sıradakine geçilir.
 * Bu liste backend'deki `services/llm_providers.py` `PROVIDER_CHAIN` ile BİREBİR
 * aynı sırada ve aynı uzunlukta olmalı: eksik bir girdi, yapılandırılmış ve fiilen
 * kullanılan bir sağlayıcının Ayarlar sayfasında hiç görünmemesine yol açar
 * (2026-09-10: `cerebras` burada yoktu, `/health/deep` 4 sağlayıcı sayarken UI 3
 * rozet gösteriyordu). */
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
    hint: 'cloud.cerebras.ai — Groq ile aynı model, ayrı ücretsiz kota.',
  },
  {
    providerName: 'github',
    settingKey: 'github_token',
    label: 'GitHub Token',
    hint: 'github.com/settings/tokens — "models: read" izniyle.',
  },
] as const

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Sağlayıcı durum rozeti.
 *
 * Eskiden yalnızca `active` bakılıyordu ve aktif OLMAYAN her yapılandırılmış sağlayıcıya
 * "Kota doldu — yedekte" deniyordu. Bu yanlıştı: zincirde aktif olan tek sağlayıcı
 * BİRİNCİ sıradaki uygun olandır, arkasındakiler kotası dolduğu için değil sırası
 * gelmediği için beklerler (2026-09-10: `cooldown_until` her ikisinde de `null` iken
 * OpenRouter ve GitHub "Kota doldu" gösteriyordu). Gerçek kota tükenmesinin tek kanıtı
 * `cooldown_until` alanıdır — backend onu yalnızca cooldown HÂLÂ sürüyorsa doldurur.
 */
function ProviderBadge({ status }: { status: LLMProviderStatus }) {
  const tone = status.active
    ? 'bg-stuhub-success/10 text-stuhub-success'
    : status.cooldown_until
      ? 'bg-stuhub-error/10 text-stuhub-error'
      : 'bg-stuhub-text-secondary/10 text-stuhub-text-secondary'
  const text = status.active
    ? 'Aktif'
    : status.cooldown_until
      ? `Kota doldu — ${new Date(status.cooldown_until).toLocaleString('tr-TR', {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        })} sonrası`
      : 'Yedekte'
  return <span className={`rounded-full px-2 py-0.5 text-xs ${tone}`}>{text}</span>
}

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
        <div className="glass-panel p-6">
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
                  {status?.configured && <ProviderBadge status={status} />}
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
                  className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
                />
                <p className="mt-1 text-xs text-stuhub-text-secondary">{field.hint}</p>
              </div>
            )
          })}
        </div>

        <div className="glass-panel p-6">
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
              className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] focus:border-stuhub-accent"
            />
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
          >
            {error}
          </p>
        )}
        {saveState === 'saved' && (
          <p
            role="status"
            className="rounded-control bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success"
          >
            Ayarlar kaydedildi.
          </p>
        )}

        <button
          type="submit"
          disabled={saveState === 'saving'}
          className="btn-primary"
        >
          {saveState === 'saving' ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
      </form>
    </section>
  )
}
