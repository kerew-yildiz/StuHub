import { useEffect, useState } from 'react'

import { settingsApi } from '../api/settings'

const MODEL_OPTIONS = [
  { value: 'deepseek-chat', label: 'DeepSeek Chat (genel amaçlı)' },
  { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner (ileri muhakeme)' },
] as const

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Ayarlar sayfası — API anahtarı + model seçimi (Faz 1.4). */
export function SettingsPage() {
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState<string>('deepseek-chat')
  const [currentKeyHint, setCurrentKeyHint] = useState('')
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [dailyGoal, setDailyGoal] = useState('3')

  useEffect(() => {
    let cancelled = false
    settingsApi
      .list()
      .then((settings) => {
        if (cancelled) return
        if (settings.model) setModel(settings.model)
        if (settings.daily_goal) setDailyGoal(settings.daily_goal)
        if (settings.deepseek_api_key) {
          setCurrentKeyHint(`${settings.deepseek_api_key} (güncel anahtar)`)
        }
        setLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setError('Ayarlar yüklenemedi. Lütfen tekrar deneyin.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaveState('saving')
    setError('')
    try {
      if (apiKey.trim()) {
        await settingsApi.set('deepseek_api_key', apiKey.trim())
      }
      await settingsApi.set('model', model)
      const goal = Number.parseInt(dailyGoal, 10)
      await settingsApi.set('daily_goal', String(Number.isNaN(goal) || goal <= 0 ? 3 : goal))
      setSaveState('saved')
      setApiKey('')
      setCurrentKeyHint('Yeni anahtar kaydedildi.')
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
        API anahtarı ve model seçimini buradan yönetebilirsin.
      </p>

      <form onSubmit={handleSave} className="mt-8 space-y-6">
        <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6">
          <h2 className="text-lg font-semibold">Yapay zeka</h2>
          <p className="mt-1 text-sm text-stuhub-text-secondary">
            Anahtar yalnızca bu cihazda (yerel veritabanında) saklanır; asla loglanmaz veya
            başka bir yere gönderilmez. Not/quiz üretimi sırasında ilgili materyal içerikleri
            yalnızca çıkarım için DeepSeek API'ye gider.
          </p>

          <div className="mt-5">
            <label htmlFor="api-key" className="mb-1 block text-sm font-medium">
              DeepSeek API anahtarı
            </label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={loaded ? currentKeyHint || 'Anahtar girin…' : 'Yükleniyor…'}
              autoComplete="off"
              className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
            />
            <p className="mt-1 text-xs text-stuhub-text-secondary">
              Mevcut anahtar yanıtta maskelenir; değiştirmek istemiyorsan boş bırak.
            </p>
          </div>

          <div className="mt-5">
            <label htmlFor="model" className="mb-1 block text-sm font-medium">
              Model
            </label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
            >
              {MODEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
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
