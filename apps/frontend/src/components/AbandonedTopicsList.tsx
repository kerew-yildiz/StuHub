import { ArrowCounterClockwise, ClockCounterClockwise, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { fetchAbandonedTopics, type AbandonedTopic } from '../api/abandoned'
import { generateErrorQuiz, type ErrorQuizResult } from '../api/errors'

export interface AbandonedTopicsListProps {
  courseId: number
  /** "Kurtarma turu başlat" tıklanınca üretilen quiz — quiz oynatma sayfasına bağlama Main'in işi. */
  onStartRecovery?: (quiz: ErrorQuizResult, topic: AbandonedTopic) => void
}

/** ISO zaman damgasını okunur tarihe çevirir; hiç çalışılmadıysa sabit metin döner. */
function formatLastActivity(value: string | null): string {
  if (!value) return 'Hiç çalışılmadı'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Hiç çalışılmadı'
  return `Son çalışma: ${parsed.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })}`
}

/** Terk edilmiş konular kurtarma listesi (Plan #50, LLM YOK — bkz. `abandoned.py`).
 *
 * Her satırın "kurtarma turu başlat" butonu, o TEK konu için hata-odaklı bir kurtarma
 * quizi üretir (`generateErrorQuiz`, Plan #6) ve sonucu `onStartRecovery` ile üst
 * bileşene teslim eder. */
export function AbandonedTopicsList({ courseId, onStartRecovery }: AbandonedTopicsListProps) {
  const [topics, setTopics] = useState<AbandonedTopic[] | null>(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setTopics(null)
    setError('')
    fetchAbandonedTopics(courseId)
      .then((result) => {
        if (!cancelled) setTopics(result)
      })
      .catch(() => {
        if (!cancelled) setError('Terk edilmiş konular alınamadı. Lütfen tekrar deneyin.')
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  async function handleStart(topic: AbandonedTopic) {
    setStarting(topic.topic)
    setError('')
    try {
      const quiz = await generateErrorQuiz(courseId, [topic.topic])
      onStartRecovery?.(quiz, topic)
    } catch {
      setError('Kurtarma turu başlatılamadı. Lütfen tekrar deneyin.')
    } finally {
      setStarting(null)
    }
  }

  if (error) {
    return (
      <div className="glass-panel flex items-center gap-2 p-5 text-sm text-stuhub-error">
        <WarningCircle size={20} aria-hidden="true" />
        {error}
      </div>
    )
  }

  if (topics === null) {
    return <div className="glass-panel p-5 text-sm text-stuhub-text-muted">Yükleniyor…</div>
  }

  if (topics.length === 0) {
    return (
      <div className="glass-panel p-5 text-sm text-stuhub-text-muted">
        Terk edilmiş bir konun yok — tüm konularla temas halindesin.
      </div>
    )
  }

  return (
    <div className="glass-panel p-5">
      <div className="mb-4 flex items-center gap-2">
        <ClockCounterClockwise size={20} className="text-stuhub-accent" aria-hidden="true" />
        <h3 className="text-sm font-medium uppercase tracking-widest text-stuhub-text-muted">
          Terk edilmiş konular
        </h3>
      </div>
      <ul className="flex flex-col gap-2">
        {topics.map((topic) => (
          <li
            key={`${topic.chapter_id}-${topic.topic}`}
            className="glass-interactive flex flex-wrap items-center justify-between gap-3 rounded-control p-3"
          >
            <div>
              <p className="text-sm text-stuhub-text">{topic.topic}</p>
              <p className="text-xs text-stuhub-text-muted">{formatLastActivity(topic.last_activity)}</p>
            </div>
            <button
              type="button"
              className="btn-primary shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={starting === topic.topic}
              onClick={() => void handleStart(topic)}
            >
              <ArrowCounterClockwise className="mr-2 h-4 w-4" aria-hidden="true" />
              {starting === topic.topic ? 'Başlatılıyor…' : 'Kurtarma turu başlat'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default AbandonedTopicsList
