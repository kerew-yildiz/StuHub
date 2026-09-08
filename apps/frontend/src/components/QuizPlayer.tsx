import { useEffect, useState } from 'react'

import {
  flattenQuestions,
  listAttempts,
  removeAttempt,
  submitAttempt,
  type AttemptOutcome,
  type Quiz,
} from '../api/quizzes'
import { confirmDialog } from '../stores/confirmStore'
import { WrongAnswerLinks } from './WrongAnswerLinks'

interface QuizPlayerProps {
  quiz: Quiz
  onDelete?: (quizId: number) => void
}

type Phase = 'loading' | 'answering' | 'finished'

/** Quiz oynatıcı — kayıtlı denemeyi geri yükler, anında feedback, tam önizleme (Faz 4 + iyileştirme). */
export function QuizPlayer({ quiz, onDelete }: QuizPlayerProps) {
  const questions = flattenQuestions(quiz)
  const [phase, setPhase] = useState<Phase>('loading')
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [answers, setAnswers] = useState<Array<{ qid: string; selected_index: number }>>([])
  const [outcome, setOutcome] = useState<AttemptOutcome | null>(null)
  const [savedAttemptId, setSavedAttemptId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Kayıtlı deneme varsa geri yükle — bitmiş quiz yeniden başlamaz (madde 6)
  useEffect(() => {
    let cancelled = false
    void listAttempts(quiz.id).then((attempts) => {
      if (cancelled || attempts.length === 0) {
        if (!cancelled) setPhase('answering')
        return
      }
      const latest = attempts[0]
      const results = latest.feedback_json?.results ?? []
      const total = flattenQuestions(quiz).length
      const correctCount = results.filter((r) => r.correct).length
      setOutcome({
        attempt_id: latest.attempt_id,
        score: latest.score ?? 0,
        total,
        correct_count: correctCount,
        results,
      })
      setSavedAttemptId(latest.attempt_id)
      setPhase('finished')
    })
    return () => {
      cancelled = true
    }
  }, [quiz.id, quiz])

  if (phase === 'loading') {
    return <p className="mt-4 text-sm text-stuhub-text-secondary">Quiz yükleniyor…</p>
  }

  const startFresh = () => {
    setOutcome(null)
    setSavedAttemptId(null)
    setCurrent(0)
    setAnswers([])
    setSelected(null)
    setRevealed(false)
    setPhase('answering')
  }

  const handleDeleteAnswers = async () => {
    if (savedAttemptId == null || !(await confirmDialog('Kayıtlı cevaplar silinecek. Emin misin?'))) return
    try {
      await removeAttempt(savedAttemptId)
      startFresh()
    } catch {
      // sessizce geç
    }
  }

  if (phase === 'finished' && outcome) {
    return (
      <div className="glass-panel mt-4 p-6">
        <h3 className="text-xl font-semibold">Quiz tamamlandı</h3>
        <p className="mt-2 text-3xl font-semibold text-stuhub-accent">
          {outcome.score} / 100
        </p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          {outcome.correct_count} / {outcome.total} doğru
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={startFresh}
            className="btn-primary"
          >
            Yeniden çöz
          </button>
          <button
            type="button"
            onClick={() => void handleDeleteAnswers()}
            className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          >
            Cevapları sil
          </button>
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(quiz.id)}
              className="rounded-control px-4 py-2 text-sm font-medium text-stuhub-error transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10"
            >
              Quiz'i sil
            </button>
          )}
        </div>

        {/* Açılır kapanır tam soru önizleme (seçeneklerle birlikte — madde 7) */}
        <details open className="glass-panel-subtle mt-5 overflow-hidden">
          <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-medium">
            Sorular ve cevaplar
          </summary>
          <div className="divide-y divide-stuhub-border">
            {outcome.results.map((result) => (
              <div key={result.qid} className="px-4 py-3 text-sm">
                <p className="font-medium">{result.question}</p>
                <div className="mt-2 space-y-1.5">
                  {result.options.map((option, index) => {
                    let className =
                      'rounded-chip border border-stuhub-border px-3 py-1.5 text-stuhub-text-secondary'
                    if (index === result.correct_index) {
                      className = 'rounded-chip border border-stuhub-success bg-stuhub-success/10 px-3 py-1.5 text-stuhub-success'
                    } else if (index === result.selected_index && !result.correct) {
                      className = 'rounded-chip border border-stuhub-error bg-stuhub-error/10 px-3 py-1.5 text-stuhub-error'
                    }
                    return (
                      <div key={index} className={className}>
                        {option}
                        {index === result.correct_index && ' ✓'}
                        {index === result.selected_index && !result.correct && ' (senin cevabın)'}
                      </div>
                    )
                  })}
                </div>
                <p
                  className={`mt-2 font-medium ${result.correct ? 'text-stuhub-success' : 'text-stuhub-error'}`}
                >
                  {result.correct ? '✓ Doğru' : '✗ Yanlış'} — {result.feedback}
                </p>
                {result.explanation && (
                  <p className="mt-1 text-stuhub-text-secondary">
                    <b>Açıklama:</b> {result.explanation}
                  </p>
                )}
                {!result.correct && (
                  <WrongAnswerLinks
                    citations={result.citations}
                    topic={questions.find((q) => q.qid === result.qid)?.question.topic}
                    chapterId={quiz.chapter_id}
                  />
                )}
              </div>
            ))}
          </div>
        </details>
      </div>
    )
  }

  const question = questions[current]
  const isLast = current === questions.length - 1
  const correct = selected === question.question.correct_index
  const feedbackText = revealed
    ? correct
      ? question.question.feedback_correct
      : question.question.feedback_wrong
    : ''

  const handleSelect = (index: number) => {
    if (revealed) return
    setSelected(index)
    setRevealed(true)
    setAnswers((prev) => [...prev, { qid: question.qid, selected_index: index }])
  }

  const handleNext = async () => {
    if (!isLast) {
      setCurrent((c) => c + 1)
      setSelected(null)
      setRevealed(false)
      return
    }
    setSubmitting(true)
    try {
      const result = await submitAttempt(quiz.id, answers)
      setOutcome(result)
      setPhase('finished')
    } catch {
      setSubmitting(false)
    }
  }

  return (
    <div className="glass-panel mt-4 p-6">
      <div className="flex items-center justify-between text-sm text-stuhub-text-secondary">
        <span>
          Soru {current + 1} / {questions.length}
        </span>
        <span>{Math.round((current / questions.length) * 100)}%</span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-pill bg-stuhub-border">
        <div
          className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
          style={{ width: `${Math.max((current / questions.length) * 100, 2)}%` }}
        />
      </div>

      <div className="mt-5">
        <p className="font-medium leading-relaxed">{question.question.question}</p>
        <div className="mt-4 space-y-2">
          {question.question.options.map((option, index) => {
            let className =
              'w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-4 py-2.5 text-left text-sm transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)]'
            if (!revealed) {
              className += ' hover:border-stuhub-border-strong hover:bg-stuhub-glass-2-hover active:scale-[0.98]'
            } else if (index === question.question.correct_index) {
              className += ' border-stuhub-success bg-stuhub-success/10 text-stuhub-success'
            } else if (index === selected && !correct) {
              className += ' border-stuhub-error bg-stuhub-error/10 text-stuhub-error'
            } else {
              className += ' opacity-60'
            }
            return (
              <button
                key={index}
                type="button"
                onClick={() => handleSelect(index)}
                disabled={revealed}
                className={className}
              >
                {option}
              </button>
            )
          })}
        </div>
      </div>

      {revealed && (
        <div
          className={`mt-4 rounded-control px-4 py-3 text-sm leading-relaxed transition-opacity duration-[var(--duration-state)] ${
            correct
              ? 'bg-stuhub-success/10 text-stuhub-success'
              : 'bg-stuhub-error/10 text-stuhub-error'
          }`}
          role="status"
        >
          <p className="font-medium">{feedbackText}</p>
          {!correct && question.question.explanation && (
            <p className="mt-1">{question.question.explanation}</p>
          )}
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={() => void handleNext()}
          disabled={!revealed || submitting}
          className="btn-primary"
        >
          {submitting ? 'Değerlendiriliyor…' : isLast ? 'Bitir' : 'Sonraki soru'}
        </button>
      </div>
    </div>
  )
}
