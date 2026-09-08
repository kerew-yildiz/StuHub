import { CheckCircle, NotePencil, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import {
  getPostmortem,
  submitPostmortem,
  type Postmortem,
  type PostmortemReason,
} from '../api/exams'

export interface MissedQuestion {
  qid: number
  question: string
}

export interface ExamPostmortemFormProps {
  examId: number
  /** Sınav sonucundan çıkarılan kaçırılan sorular (mcq/tf/fib: `correct === false`;
   * open: `score < 10`) — üretimi çağıran sayfanın sorumluluğundadır. */
  missedQuestions: MissedQuestion[]
  /** Kaydedilip LLM özeti üretildikten sonra çağrılır. */
  onSubmitted?: (postmortem: Postmortem) => void
}

const REASON_OPTIONS: Array<{ value: PostmortemReason; label: string }> = [
  { value: 'bilmiyordum', label: 'Bilmiyordum' },
  { value: 'karıştırdım', label: 'Karıştırdım' },
  { value: 'süre_yetmedi', label: 'Süre yetmedi' },
  { value: 'dikkatsizlik', label: 'Dikkatsizlik' },
]

/** Sınav sonrası muhasebe formu (Plan #44) — her kaçırılan soru için sebep seçimi, gönderince
 * backend'in tek cümlelik LLM özetini gösterir. Daha önce gönderilmişse (sayfa yenilense bile)
 * kayıtlı özeti salt-okunur gösterir; sınav başına tek muhasebe kaydı vardır. */
export function ExamPostmortemForm({ examId, missedQuestions, onSubmitted }: ExamPostmortemFormProps) {
  const [existing, setExisting] = useState<Postmortem | null | undefined>(undefined)
  const [reasons, setReasons] = useState<Record<number, PostmortemReason>>({})
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [result, setResult] = useState<Postmortem | null>(null)

  useEffect(() => {
    let cancelled = false
    void getPostmortem(examId).then((found) => {
      if (!cancelled) setExisting(found)
    })
    return () => {
      cancelled = true
    }
  }, [examId])

  if (existing === undefined) {
    return <p className="mt-4 text-sm text-stuhub-text-secondary">Muhasebe durumu kontrol ediliyor…</p>
  }

  const saved = result ?? existing
  if (saved) {
    return (
      <div className="glass-panel mt-4 p-6">
        <div className="flex items-center gap-2">
          <NotePencil size={20} className="text-stuhub-accent" />
          <h3 className="text-lg font-semibold">Sınav sonrası muhasebe</h3>
        </div>
        <div className="mt-3 rounded-control bg-stuhub-info/10 p-3 text-sm text-stuhub-text">
          {saved.summary}
        </div>
        <ul className="mt-3 space-y-1.5 text-sm text-stuhub-text-secondary">
          {saved.items.map((item, index) => (
            <li key={index}>
              {item.question} → <b>{REASON_OPTIONS.find((r) => r.value === item.reason)?.label}</b>
            </li>
          ))}
        </ul>
      </div>
    )
  }

  if (missedQuestions.length === 0) {
    return (
      <div className="glass-panel mt-4 flex items-center gap-2 p-6 text-stuhub-success">
        <CheckCircle size={20} weight="fill" />
        <p className="font-medium">Hiç soru kaçırmadın — muhasebeye gerek yok.</p>
      </div>
    )
  }

  const allAnswered = missedQuestions.every((q) => reasons[q.qid])

  const handleSubmit = async () => {
    setSubmitting(true)
    setErrorMessage('')
    try {
      const items = missedQuestions.map((q) => ({ question: q.question, reason: reasons[q.qid] }))
      const postmortem = await submitPostmortem(examId, items)
      setResult(postmortem)
      onSubmitted?.(postmortem)
    } catch {
      setErrorMessage('Muhasebe kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass-panel mt-4 p-6">
      <div className="flex items-center gap-2">
        <NotePencil size={20} className="text-stuhub-accent" />
        <h3 className="text-lg font-semibold">Sınav sonrası muhasebe</h3>
      </div>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Kaçırdığın {missedQuestions.length} soru için sebebini işaretle; sonraki döneme
        tek cümlelik bir tavsiye üretilecek.
      </p>

      <div className="mt-4 space-y-4">
        {missedQuestions.map((q) => (
          <div key={q.qid} className="rounded-control border border-stuhub-border bg-stuhub-glass-2 p-4">
            <p className="text-sm font-medium leading-relaxed">{q.question}</p>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {REASON_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setReasons((prev) => ({ ...prev, [q.qid]: option.value }))}
                  className={`rounded-chip border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-micro)] ${
                    reasons[q.qid] === option.value
                      ? 'border-stuhub-accent bg-stuhub-accent/10 text-stuhub-text'
                      : 'border-stuhub-border text-stuhub-text-secondary hover:border-stuhub-border-strong'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {errorMessage && (
        <div className="mt-3 flex items-center gap-2 text-sm text-stuhub-error">
          <WarningCircle size={16} />
          {errorMessage}
        </div>
      )}

      <button
        type="button"
        onClick={() => void handleSubmit()}
        disabled={!allAnswered || submitting}
        className="btn-primary mt-4"
      >
        {submitting ? 'Kaydediliyor…' : 'Muhasebeyi Kaydet'}
      </button>
    </div>
  )
}

export default ExamPostmortemForm
