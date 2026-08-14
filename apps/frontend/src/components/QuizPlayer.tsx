import { useState } from 'react'

import {
  flattenQuestions,
  submitAttempt,
  type AttemptOutcome,
  type Quiz,
  type QuizCitation,
} from '../api/quizzes'
import { CitationPopup } from './CitationPopup'

interface QuizPlayerProps {
  quiz: Quiz
  onReset?: () => void
}

/** Quiz oynatıcı — tek soru/ekran, anında feedback, ilerleme (stil rehberi + Faz 4.2). */
export function QuizPlayer({ quiz, onReset }: QuizPlayerProps) {
  const questions = flattenQuestions(quiz)
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [answers, setAnswers] = useState<Array<{ qid: string; selected_index: number }>>([])
  const [outcome, setOutcome] = useState<AttemptOutcome | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [activeCitation, setActiveCitation] = useState<QuizCitation | null>(null)

  if (outcome) {
    return (
      <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6">
        <h3 className="text-xl font-semibold">Quiz tamamlandı</h3>
        <p className="mt-2 text-3xl font-semibold text-stuhub-accent">
          {outcome.score} / 100
        </p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          {outcome.correct_count} / {outcome.total} doğru
        </p>
        <button
          type="button"
          onClick={() => {
            setOutcome(null)
            setCurrent(0)
            setAnswers([])
            setSelected(null)
            setRevealed(false)
            onReset?.()
          }}
          className="mt-4 rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
        >
          Tekrar dene
        </button>

        {/* Açılır kapanır soru önizleme penceresi */}
        <details open className="mt-5 rounded-md border border-stuhub-border">
          <summary className="cursor-pointer select-none bg-stuhub-bg px-4 py-2.5 text-sm font-medium">
            Sorular ve cevaplar
          </summary>
          <div className="divide-y divide-stuhub-border">
            {outcome.results.map((result) => {
              const selectedLabel = result.options[result.selected_index] ?? '-'
              const correctLabel = result.options[result.correct_index] ?? '-'
              return (
                <div key={result.qid} className="px-4 py-3 text-sm">
                  <p className="font-medium">{result.question}</p>
                  <p className="mt-1 text-stuhub-text-secondary">
                    Senin cevabın: <b>{selectedLabel}</b>
                    {!result.correct && (
                      <>
                        {' · '}Doğru cevap: <b className="text-stuhub-success">{correctLabel}</b>
                      </>
                    )}
                  </p>
                  <p
                    className={`mt-1 ${result.correct ? 'text-stuhub-success' : 'text-stuhub-error'}`}
                  >
                    {result.correct ? '✓ Doğru' : '✗ Yanlış'} — {result.feedback}
                  </p>
                  {!result.correct && result.explanation && (
                    <p className="mt-1 text-stuhub-text-secondary">{result.explanation}</p>
                  )}
                </div>
              )
            })}
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
    } catch {
      setSubmitting(false)
      // hata: kullanıcı tekrar bitir'e basabilir
    }
  }

  return (
    <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6">
      <div className="flex items-center justify-between text-sm text-stuhub-text-secondary">
        <span>
          Soru {current + 1} / {questions.length}
        </span>
        <span>{Math.round((current / questions.length) * 100)}%</span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stuhub-border">
        <div
          className="h-full bg-stuhub-accent transition-all duration-300"
          style={{ width: `${Math.max((current / questions.length) * 100, 2)}%` }}
        />
      </div>

      <div className="mt-5">
        <p className="font-medium leading-relaxed">{question.question.question}</p>
        <div className="mt-4 space-y-2">
          {question.question.options.map((option, index) => {
            let className =
              'w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-4 py-2.5 text-left text-sm transition-colors duration-150'
            if (!revealed) {
              className += ' hover:border-stuhub-accent'
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
          className={`mt-4 rounded-sm px-4 py-3 text-sm leading-relaxed ${
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
          {question.question.citations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {question.question.citations.map((citation) => (
                <button
                  key={citation.id}
                  type="button"
                  onClick={() => setActiveCitation(citation)}
                  className="rounded-sm bg-stuhub-surface px-2 py-1 text-xs font-semibold text-stuhub-accent transition-colors duration-150 hover:bg-stuhub-surface-hover"
                >
                  [{citation.id}]
                  {citation.page != null ? ` sayfa ${citation.page}` : ''}
                  {citation.slide != null ? ` slide ${citation.slide}` : ''}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={() => void handleNext()}
          disabled={!revealed || submitting}
          className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
        >
          {submitting ? 'Değerlendiriliyor…' : isLast ? 'Bitir' : 'Sonraki soru'}
        </button>
      </div>

      {activeCitation && (
        <CitationPopup citation={activeCitation} onClose={() => setActiveCitation(null)} />
      )}
    </div>
  )
}
