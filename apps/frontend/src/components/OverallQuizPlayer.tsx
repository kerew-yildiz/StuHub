import { useEffect, useState } from 'react'

import {
  listOverallAttempts,
  removeOverallAttempt,
  submitOverallAttempt,
  type OverallOutcome,
  type OverallQuestion,
  type OverallQuiz,
} from '../api/overall'

interface OverallQuizPlayerProps {
  quiz: OverallQuiz
  onDelete?: (quizId: number) => void
}

type AnswerValue = number | string

interface LocalResult {
  correct: boolean
  feedback: string
  explanation: string
  citations: OverallQuestion['citations']
  acceptedAnswers?: string[]
}

const TYPE_LABELS: Record<string, string> = {
  mcq: 'Çoktan seçmeli',
  tf: 'Doğru-Yanlış',
  fib: 'Boşluk doldurma',
  open: 'Açık uçlu',
}

/** Genel quiz oynatıcı — kayıtlı denemeyi geri yükler, 55 soru, 4 tip (Faz 5 + iyileştirme). */
export function OverallQuizPlayer({ quiz, onDelete }: OverallQuizPlayerProps) {
  const questions = quiz.questions_json.questions
  const [phase, setPhase] = useState<'loading' | 'answering' | 'finished'>('loading')
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Array<{ qid: number; value: AnswerValue }>>([])
  const [local, setLocal] = useState<LocalResult | null>(null)
  const [openText, setOpenText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [outcome, setOutcome] = useState<OverallOutcome | null>(null)
  const [savedAttemptId, setSavedAttemptId] = useState<number | null>(null)

  // Kayıtlı deneme varsa geri yükle — bitmiş quiz yeniden başlamaz (madde 6)
  useEffect(() => {
    let cancelled = false
    void listOverallAttempts(quiz.id).then((attempts) => {
      if (cancelled || attempts.length === 0) {
        if (!cancelled) setPhase('answering')
        return
      }
      setOutcome(attempts[0].score_json)
      setSavedAttemptId(attempts[0].attempt_id)
      setPhase('finished')
    })
    return () => {
      cancelled = true
    }
  }, [quiz.id])

  if (phase === 'loading') {
    return <p className="mt-4 text-sm text-stuhub-text-secondary">Genel quiz yükleniyor…</p>
  }

  const startFresh = () => {
    setOutcome(null)
    setSavedAttemptId(null)
    setCurrent(0)
    setAnswers([])
    setLocal(null)
    setOpenText('')
    setPhase('answering')
  }

  const handleDeleteAnswers = async () => {
    if (savedAttemptId == null || !window.confirm('Kayıtlı cevaplar silinecek. Emin misin?')) return
    try {
      await removeOverallAttempt(savedAttemptId)
      startFresh()
    } catch {
      // sessizce geç
    }
  }

  if (phase === 'finished' && outcome) {
    return (
      <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6">
        <h3 className="text-xl font-semibold">Genel quiz tamamlandı</h3>
        <p className="mt-2 text-3xl font-semibold text-stuhub-accent">{outcome.score} / 100</p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Kapalı sorular: {outcome.closed_correct} / {outcome.closed_total} doğru · Açık uçlu
          toplam: {outcome.open_total} / 50
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={startFresh}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
          >
            Yeniden çöz
          </button>
          <button
            type="button"
            onClick={() => void handleDeleteAnswers()}
            className="rounded-sm border border-stuhub-border px-4 py-2 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
          >
            Cevapları sil
          </button>
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(quiz.id)}
              className="rounded-sm px-4 py-2 text-sm font-medium text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
            >
              Genel quiz'i sil
            </button>
          )}
        </div>

        {/* Açılır kapanır tam soru önizleme (madde 3: soru + seçenekler + cevap + feedback) */}
        <div className="mt-5 space-y-3">
          <details open className="rounded-md border border-stuhub-border">
            <summary className="cursor-pointer select-none bg-stuhub-bg px-4 py-2.5 text-sm font-medium">
              Sorular ve cevaplar ({outcome.results.length})
            </summary>
            <div className="space-y-4 p-4">
              {outcome.results.map((result) => (
                <div
                  key={result.qid}
                  className="rounded-md border border-stuhub-border bg-stuhub-bg p-4"
                >
                  <p className="text-sm font-medium leading-relaxed">{result.question}</p>

                  {result.type === 'mcq' && result.options && (
                    <div className="mt-2 space-y-1.5">
                      {result.options.map((option, index) => {
                        const isCorrect = index === result.correct_index
                        const isSelected = index === result.selected_index
                        let className =
                          'rounded-sm border border-stuhub-border px-3 py-1.5 text-stuhub-text-secondary'
                        if (isCorrect) {
                          className =
                            'rounded-sm border border-stuhub-success bg-stuhub-success/10 px-3 py-1.5 text-stuhub-success'
                        } else if (isSelected) {
                          className =
                            'rounded-sm border border-stuhub-error bg-stuhub-error/10 px-3 py-1.5 text-stuhub-error'
                        }
                        return (
                          <div key={index} className={className}>
                            {option}
                            {isCorrect && ' ✓ (doğru cevap)'}
                            {isSelected && !isCorrect && ' ← senin cevabın'}
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {result.type === 'tf' && result.statement != null && (
                    <div className="mt-2 rounded-sm border border-stuhub-border px-3 py-2 text-stuhub-text-secondary">
                      Senin cevabın: <b>{result.selected_tf === 1 ? 'Doğru' : 'Yanlış'}</b>
                      {result.selected_tf !== (result.answer ? 1 : 0) && (
                        <>
                          {' · '}
                          Doğru cevap: <b className="text-stuhub-success">{result.answer ? 'Doğru' : 'Yanlış'}</b>
                        </>
                      )}
                    </div>
                  )}

                  {result.type === 'fib' && (
                    <div className="mt-2 rounded-sm border border-stuhub-border px-3 py-2 text-stuhub-text-secondary">
                      Senin cevabın: “{result.user_answer}”
                      {!result.correct && (
                        <>
                          {' · '}Doğru cevap:{' '}
                          <b className="text-stuhub-success">
                            {(result.accepted_answers ?? []).join(' / ') || '—'}
                          </b>
                        </>
                      )}
                    </div>
                  )}

                  {result.type === 'open' && (
                    <div className="mt-2 rounded-sm border border-stuhub-border px-3 py-2 text-stuhub-text-secondary">
                      Senin cevabın: “{(result.user_answer ?? '').slice(0, 160)}”
                    </div>
                  )}

                  <div
                    className={`mt-2 rounded-sm px-3 py-2 text-sm leading-relaxed ${
                      result.type === 'open'
                        ? 'bg-stuhub-info/10 text-stuhub-text'
                        : result.correct
                          ? 'bg-stuhub-success/10 text-stuhub-success'
                          : 'bg-stuhub-error/10 text-stuhub-error'
                    }`}
                  >
                    <p className="font-medium">
                      {result.type === 'open'
                        ? `Puan: ${result.score} / 10`
                        : result.correct
                          ? '✓ Doğru'
                          : '✗ Yanlış'}
                      {result.feedback ? ` — ${result.feedback}` : ''}
                    </p>
                    {/* Açıklama her durumda gösterilir: doğruysa neden doğru, yanlışsa öğretici metin */}
                    {result.explanation && (
                      <p className="mt-1">
                        <b>Açıklama:</b> {result.explanation}
                      </p>
                    )}
                  </div>

                  {result.grade && (
                    <div className="mt-2 space-y-1 text-sm text-stuhub-text-secondary">
                      <p>
                        <b>Doğru:</b> {result.grade.correct.join(', ') || 'yok'}
                      </p>
                      <p>
                        <b>Eksik:</b> {result.grade.missing.join(', ') || 'yok'}
                      </p>
                      <p>
                        <b>Yanlış:</b> {result.grade.incorrect.join(', ') || 'yok'}
                      </p>
                      <p>
                        <b>Gereksiz:</b> {result.grade.unnecessary.join(', ') || 'yok'}
                      </p>
                      <p className="mt-1">{result.grade.explanation}</p>
                      {result.grade.ideal_answer && (
                        <div className="mt-2 rounded-sm bg-stuhub-surface p-3">
                          <p className="font-medium">İdeal cevap:</p>
                          <p className="mt-1">{result.grade.ideal_answer}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    )
  }

  const question = questions[current]
  const isLast = current === questions.length - 1

  const evaluateClosed = (value: number): LocalResult => {
    let correct: boolean
    if (question.type === 'mcq') {
      correct = value === question.correct_index
    } else {
      correct = (value === 1) === question.answer
    }
    return {
      correct,
      feedback: correct ? (question.feedback_correct ?? '') : (question.feedback_wrong ?? ''),
      explanation: question.explanation ?? '',
      citations: question.citations ?? [],
    }
  }

  const handleSelect = (value: number) => {
    if (local) return
    setLocal(evaluateClosed(value))
    setAnswers((prev) => [...prev, { qid: current, value }])
  }

  const handleFibChange = (text: string) => {
    setAnswers((prev) => [...prev.filter((a) => a.qid !== current), { qid: current, value: text }])
  }

  const handleOpenChange = (text: string) => {
    setOpenText(text)
    setAnswers((prev) => [...prev.filter((a) => a.qid !== current), { qid: current, value: text }])
  }

  const handleNext = async () => {
    if (!isLast) {
      setCurrent((c) => c + 1)
      setLocal(null)
      setOpenText('')
      return
    }
    setSubmitting(true)
    try {
      const result = await submitOverallAttempt(quiz.id, answers)
      setOutcome(result)
      setPhase('finished')
    } catch {
      setSubmitting(false)
    }
  }

  const answered = answers.some((a) => a.qid === current)
  const canNext =
    question.type === 'open'
      ? (answers.find((a) => a.qid === current)?.value ?? '') !== ''
      : question.type === 'fib'
        ? (answers.find((a) => a.qid === current)?.value ?? '') !== ''
        : local !== null

  return (
    <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6">
      <div className="flex items-center justify-between text-sm text-stuhub-text-secondary">
        <span>
          Soru {current + 1} / {questions.length} · {TYPE_LABELS[question.type]}
        </span>
        <span>{Math.round((current / questions.length) * 100)}%</span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stuhub-border">
        <div
          className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
          style={{ width: `${Math.max((current / questions.length) * 100, 2)}%` }}
        />
      </div>

      <div className="mt-5">
        <p className="font-medium leading-relaxed">
          {question.type === 'mcq'
            ? question.question
            : question.type === 'tf'
              ? question.statement
              : question.type === 'open'
                ? question.question
                : question.text}
        </p>

        {question.type === 'mcq' && (
          <div className="mt-4 space-y-2">
            {(question.options ?? []).map((option, index) => {
              let className =
                'w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-4 py-2.5 text-left text-sm transition-colors duration-150'
              if (!local) {
                className += ' hover:border-stuhub-accent'
              } else if (index === question.correct_index) {
                className += ' border-stuhub-success bg-stuhub-success/10 text-stuhub-success'
              } else if (index === (answers.find((a) => a.qid === current)?.value as number) && !local.correct) {
                className += ' border-stuhub-error bg-stuhub-error/10 text-stuhub-error'
              } else {
                className += ' opacity-60'
              }
              return (
                <button
                  key={index}
                  type="button"
                  onClick={() => handleSelect(index)}
                  disabled={local !== null}
                  className={className}
                >
                  {option}
                </button>
              )
            })}
          </div>
        )}

        {question.type === 'tf' && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              { label: 'Doğru', value: 1 },
              { label: 'Yanlış', value: 0 },
            ].map((option) => {
              const selectedValue = answers.find((a) => a.qid === current)?.value as number
              let className =
                'rounded-sm border border-stuhub-border bg-stuhub-bg px-4 py-2.5 text-sm font-medium transition-colors duration-150'
              if (!local) {
                className += ' hover:border-stuhub-accent'
              } else if (option.value === (question.answer ? 1 : 0)) {
                className += ' border-stuhub-success bg-stuhub-success/10 text-stuhub-success'
              } else if (option.value === selectedValue && !local.correct) {
                className += ' border-stuhub-error bg-stuhub-error/10 text-stuhub-error'
              } else {
                className += ' opacity-60'
              }
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  disabled={local !== null}
                  className={className}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        )}

        {question.type === 'fib' && (
          <input
            type="text"
            value={(answers.find((a) => a.qid === current)?.value as string) ?? ''}
            onChange={(e) => handleFibChange(e.target.value)}
            disabled={local !== null}
            placeholder="Cevabını yaz…"
            className="mt-4 w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-4 py-2.5 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
          />
        )}

        {question.type === 'open' && (
          <textarea
            value={openText}
            onChange={(e) => handleOpenChange(e.target.value)}
            rows={5}
            placeholder="Cevabını yaz… (değerlendirme quiz sonunda yapılır)"
            className="mt-4 w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-4 py-2.5 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
          />
        )}
      </div>

      {local && (
        <div
          className={`mt-4 rounded-sm px-4 py-3 text-sm leading-relaxed ${
            local.correct
              ? 'bg-stuhub-success/10 text-stuhub-success'
              : 'bg-stuhub-error/10 text-stuhub-error'
          }`}
          role="status"
        >
          <p className="font-medium">{local.feedback}</p>
          {!local.correct && local.explanation && <p className="mt-1">{local.explanation}</p>}
        </div>
      )}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={() => void handleNext()}
          disabled={!canNext || submitting || !answered}
          className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
        >
          {submitting ? 'Değerlendiriliyor…' : isLast ? 'Quiz\'i Bitir' : 'Sonraki soru'}
        </button>
      </div>
    </div>
  )
}
