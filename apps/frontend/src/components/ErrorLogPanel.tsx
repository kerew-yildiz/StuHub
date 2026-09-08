import { ArrowRight, Funnel, Repeat, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { listErrors, type ErrorLogEntry } from '../api/errors'

export interface ErrorLogPanelProps {
  courseId: number
}

const CONTROL_CLASS =
  'rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] focus:border-stuhub-accent'

/** Kayıt tarihini (SQLite 'YYYY-MM-DD HH:MM:SS' / ISO) tr-TR biçiminde gösterir. */
function formatDate(value: string): string {
  const parsed = new Date(value.includes('T') ? value : value.replace(' ', 'T') + 'Z')
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Hata günlüğü — geçmiş quiz denemelerindeki yanlış cevaplar, konu/tarih süzgeçli (plan #5). */
export function ErrorLogPanel({ courseId }: ErrorLogPanelProps) {
  const [entries, setEntries] = useState<ErrorLogEntry[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [topic, setTopic] = useState('')
  const [since, setSince] = useState('')
  const [onlyRepeated, setOnlyRepeated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void (async () => {
      try {
        const data = await listErrors(courseId, { topic, since, onlyRepeated })
        if (cancelled) return
        setEntries(data)
        // Süzgeç yoksa yanıt tüm hataları içerir: konu listesi buradan beslenir
        if (!topic && !onlyRepeated) {
          setTopics([...new Set(data.map((entry) => entry.topic))].sort((a, b) => a.localeCompare(b, 'tr')))
        }
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Hata günlüğü alınamadı.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [courseId, topic, since, onlyRepeated])

  const hasFilter = Boolean(topic || since || onlyRepeated)

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Hatalarım</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Quizlerde yanlış cevapladığın sorular burada toplanır. Aynı konuda birden fazla hata
        yaptıysan, o konu tekrar çalışman gereken yerdir.
      </p>

      <div className="glass-panel-subtle mt-4 flex flex-wrap items-center gap-3 px-4 py-3">
        <Funnel className="h-4 w-4 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
        <label className="flex items-center gap-2 text-sm text-stuhub-text-secondary">
          Konu
          <select
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            className={CONTROL_CLASS}
            aria-label="Konuya göre süz"
          >
            <option value="">Tümü</option>
            {topics.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm text-stuhub-text-secondary">
          Şu tarihten sonra
          <input
            type="date"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            className={CONTROL_CLASS}
            aria-label="Tarihe göre süz"
          />
        </label>

        <button
          type="button"
          onClick={() => setOnlyRepeated((value) => !value)}
          aria-pressed={onlyRepeated}
          className={`glass-interactive flex items-center gap-2 rounded-pill px-3.5 py-1.5 text-sm font-medium ${
            onlyRepeated
              ? 'border border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
              : 'glass-panel-subtle border border-transparent text-stuhub-text-secondary'
          }`}
        >
          <Repeat className="h-4 w-4" aria-hidden="true" />
          Sadece tekrar edenler
        </button>

        {hasFilter && (
          <button
            type="button"
            onClick={() => {
              setTopic('')
              setSince('')
              setOnlyRepeated(false)
            }}
            className="text-sm text-stuhub-text-secondary underline decoration-dotted"
          >
            Süzgeçleri temizle
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {loading && <p className="mt-4 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}

      {!loading && !error && entries.length === 0 && (
        <div className="glass-panel mt-4 flex items-start gap-3 px-5 py-4">
          <WarningCircle className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
          <p className="text-sm text-stuhub-text-secondary">
            {hasFilter
              ? 'Bu süzgeçlerle eşleşen hata yok. Süzgeçleri gevşetip tekrar dene.'
              : 'Henüz hata kaydı yok. Bir quiz çözdükten sonra yanlış cevapladığın sorular burada birikir.'}
          </p>
        </div>
      )}

      {!loading && entries.length > 0 && (
        <div className="mt-4 space-y-3">
          {entries.map((entry, index) => (
            <article
              key={`${entry.quiz_id}-${entry.created_at}-${index}`}
              className="glass-panel px-5 py-4"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-stuhub-text-secondary">
                <span className="glass-panel-subtle rounded-pill px-2.5 py-1 font-medium text-stuhub-text">
                  {entry.topic}
                </span>
                <span>{formatDate(entry.created_at)}</span>
                <span>{entry.chapter_id === null ? 'Genel quiz' : 'Bölüm quizi'}</span>
                {entry.repeat_count > 1 && (
                  <span className="flex items-center gap-1 rounded-pill border border-stuhub-accent-glass-border bg-stuhub-accent-glass px-2.5 py-1 font-medium text-stuhub-text">
                    <Repeat className="h-3 w-3" aria-hidden="true" />
                    {entry.repeat_count} kez yanlış
                  </span>
                )}
              </div>

              <p className="mt-3 text-sm font-medium">{entry.question_text}</p>

              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-control bg-stuhub-error/10 px-3 py-1.5 text-stuhub-error">
                  {entry.given_answer}
                </span>
                <ArrowRight className="h-4 w-4 text-stuhub-text-secondary" aria-hidden="true" />
                <span className="rounded-control bg-stuhub-success/10 px-3 py-1.5 text-stuhub-success">
                  {entry.correct_answer}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default ErrorLogPanel
