import { LockSimple, Timer, WarningCircle } from '@phosphor-icons/react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { startExamSimulation } from '../api/exams'
import { submitOverallAttempt, type OverallOutcome, type OverallQuiz } from '../api/overall'

export interface ExamSimulationPlayerProps {
  courseId: number
  examId: number
  examTitle: string
  /** Sınav puanlandığında çağrılır — kaçırılan soruları muhasebe formuna (Plan #44) aktarmak için. */
  onFinished?: (outcome: OverallOutcome, quiz: OverallQuiz) => void
}

/** Sınav süresi sabit 60 dakika — gerçek sınav provası için makul bir üst sınır (55 soru).
 * Backend süreyi zorlamaz, yalnızca `duration_sec` olarak kaydeder; zamanlayıcı burada işler. */
const EXAM_DURATION_SEC = 60 * 60
const WARNING_THRESHOLD_SEC = 5 * 60

const TYPE_LABELS: Record<string, string> = {
  mcq: 'Çoktan seçmeli',
  tf: 'Doğru-Yanlış',
  fib: 'Boşluk doldurma',
  open: 'Açık uçlu',
}

type Phase = 'generating' | 'answering' | 'submitting' | 'finished' | 'error'

function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, totalSeconds)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

/** Sınav simülasyonu oynatıcısı (Plan #35) — süreli, karışık, geri dönüşsüz, anlık feedback
 * yok. `OverallQuizPlayer`'ın görsel dilini paylaşır ama ayrı bir akış yönetir: quiz burada
 * `mode='exam'` ile üretilir, sorularda cevabı açığa çıkaran alanlar zaten yoktur (backend
 * süzer), bu yüzden seçim yapıldığında doğru/yanlış gösterilmez — sonuç yalnızca sınav
 * bitince (`submitOverallAttempt`) görünür. */
export function ExamSimulationPlayer({ courseId, examId, examTitle, onFinished }: ExamSimulationPlayerProps) {
  const [phase, setPhase] = useState<Phase>('generating')
  const [percent, setPercent] = useState(0)
  const [statusMessage, setStatusMessage] = useState('Sınav hazırlanıyor…')
  const [errorMessage, setErrorMessage] = useState('')
  const [quiz, setQuiz] = useState<OverallQuiz | null>(null)
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Array<{ qid: number; value: number | string }>>([])
  const [openText, setOpenText] = useState('')
  const [outcome, setOutcome] = useState<OverallOutcome | null>(null)
  const [remainingSec, setRemainingSec] = useState(EXAM_DURATION_SEC)
  const [retryTick, setRetryTick] = useState(0)
  const startedAtRef = useRef<number | null>(null)
  const submittingRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    setPhase('generating')
    setPercent(0)
    setStatusMessage('Sınav hazırlanıyor…')
    void startExamSimulation(courseId, examId, {
      onStatus: (p, message) => {
        if (cancelled) return
        setPercent(p)
        setStatusMessage(message)
      },
      onDone: (generatedQuiz) => {
        if (cancelled) return
        setQuiz(generatedQuiz)
        startedAtRef.current = Date.now()
        setRemainingSec(EXAM_DURATION_SEC)
        setPhase('answering')
      },
      onError: (message) => {
        if (cancelled) return
        setErrorMessage(message)
        setPhase('error')
      },
    })
    return () => {
      cancelled = true
    }
  }, [courseId, examId, retryTick])

  const questions = quiz?.questions_json.questions ?? []

  const finishExam = useCallback(
    async (finalAnswers: Array<{ qid: number; value: number | string }>) => {
      if (submittingRef.current || !quiz) return
      submittingRef.current = true
      setPhase('submitting')
      const elapsed = startedAtRef.current
        ? Math.round((Date.now() - startedAtRef.current) / 1000)
        : EXAM_DURATION_SEC
      try {
        const result = await submitOverallAttempt(quiz.id, finalAnswers, Math.min(elapsed, EXAM_DURATION_SEC))
        setOutcome(result)
        setPhase('finished')
        onFinished?.(result, quiz)
      } catch {
        setErrorMessage('Sınav gönderilemedi. Lütfen tekrar deneyin.')
        setPhase('error')
      } finally {
        submittingRef.current = false
      }
    },
    [onFinished, quiz],
  )

  // Sayaç — yalnızca cevaplama fazında işler, süre bitince mevcut cevaplarla otomatik gönderir.
  useEffect(() => {
    if (phase !== 'answering') return
    const id = window.setInterval(() => {
      setRemainingSec((prev) => {
        if (prev <= 1) {
          window.clearInterval(id)
          void finishExam(answers)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `answers` kasıtlı: süre dolunca son hali gönderilir
  }, [phase, finishExam])

  if (phase === 'generating') {
    return (
      <div className="glass-panel mt-4 p-6">
        <h3 className="text-lg font-semibold">{examTitle} — sınav simülasyonu hazırlanıyor</h3>
        <p className="mt-1 text-sm text-stuhub-text-secondary">{statusMessage}</p>
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-pill bg-stuhub-border">
          <div
            className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
            style={{ width: `${Math.max(percent, 2)}%` }}
          />
        </div>
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="glass-panel mt-4 p-6">
        <div className="flex items-center gap-2 text-stuhub-error">
          <WarningCircle size={20} weight="fill" />
          <p className="font-medium">{errorMessage || 'Sınav simülasyonu başarısız oldu.'}</p>
        </div>
        <button
          type="button"
          onClick={() => setRetryTick((t) => t + 1)}
          className="btn-primary mt-4"
        >
          Tekrar dene
        </button>
      </div>
    )
  }

  if (phase === 'submitting') {
    return <p className="mt-4 text-sm text-stuhub-text-secondary">Sınav değerlendiriliyor…</p>
  }

  if (phase === 'finished' && outcome) {
    return (
      <div className="glass-panel mt-4 p-6">
        <h3 className="text-xl font-semibold">{examTitle} tamamlandı</h3>
        <p className="mt-2 text-3xl font-semibold text-stuhub-accent">{outcome.score} / 100</p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Kapalı sorular: {outcome.closed_correct} / {outcome.closed_total} doğru · Açık uçlu
          toplam: {outcome.open_total} / 50
          {outcome.duration_sec != null && <> · Süre: {formatClock(outcome.duration_sec)}</>}
        </p>
        <div className="mt-5 space-y-3">
          <details open className="glass-panel-subtle overflow-hidden">
            <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-medium">
              Sorular ve cevaplar ({outcome.results.length})
            </summary>
            <div className="space-y-4 p-4">
              {outcome.results.map((result) => (
                <div
                  key={result.qid}
                  className="rounded-control border border-stuhub-border bg-stuhub-glass-2 p-4"
                >
                  <p className="text-sm font-medium leading-relaxed">{result.question}</p>
                  <div
                    className={`mt-2 rounded-control px-3 py-2 text-sm leading-relaxed ${
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
                    </p>
                    {result.explanation && <p className="mt-1">{result.explanation}</p>}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    )
  }

  const question = questions[current]
  if (!question) return null
  const isLast = current === questions.length - 1
  const selectedValue = answers.find((a) => a.qid === current)?.value
  const answered = selectedValue !== undefined && selectedValue !== ''
  const timeCritical = remainingSec <= WARNING_THRESHOLD_SEC

  const setAnswer = (value: number | string) => {
    setAnswers((prev) => [...prev.filter((a) => a.qid !== current), { qid: current, value }])
  }

  const handleNext = () => {
    if (isLast) {
      void finishExam(answers)
      return
    }
    setCurrent((c) => c + 1)
    setOpenText('')
  }

  return (
    <div className="glass-panel mt-4 p-6">
      <div className="flex items-center justify-between text-sm text-stuhub-text-secondary">
        <span className="flex items-center gap-1.5">
          <LockSimple size={14} />
          Soru {current + 1} / {questions.length} · {TYPE_LABELS[question.type]}
        </span>
        <span
          className={`flex items-center gap-1.5 font-medium ${
            timeCritical ? 'text-stuhub-error' : 'text-stuhub-text'
          }`}
        >
          <Timer size={16} weight={timeCritical ? 'fill' : 'regular'} />
          {formatClock(remainingSec)}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-pill bg-stuhub-border">
        <div
          className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
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
            {(question.options ?? []).map((option, index) => (
              <button
                key={index}
                type="button"
                onClick={() => setAnswer(index)}
                className={`w-full rounded-control border px-4 py-2.5 text-left text-sm transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] ${
                  selectedValue === index
                    ? 'border-stuhub-accent bg-stuhub-accent/10 text-stuhub-text'
                    : 'border-stuhub-border bg-stuhub-glass-2 hover:border-stuhub-border-strong hover:bg-stuhub-glass-2-hover active:scale-[0.98]'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        )}

        {question.type === 'tf' && (
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              { label: 'Doğru', value: 1 },
              { label: 'Yanlış', value: 0 },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setAnswer(option.value)}
                className={`rounded-control border px-4 py-2.5 text-sm font-medium transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] ${
                  selectedValue === option.value
                    ? 'border-stuhub-accent bg-stuhub-accent/10 text-stuhub-text'
                    : 'border-stuhub-border bg-stuhub-glass-2 hover:border-stuhub-border-strong hover:bg-stuhub-glass-2-hover active:scale-[0.98]'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}

        {question.type === 'fib' && (
          <input
            type="text"
            value={(selectedValue as string) ?? ''}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Cevabını yaz…"
            className="mt-4 w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-4 py-2.5 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
          />
        )}

        {question.type === 'open' && (
          <textarea
            value={openText}
            onChange={(e) => {
              setOpenText(e.target.value)
              setAnswer(e.target.value)
            }}
            rows={5}
            placeholder="Cevabını yaz… (değerlendirme sınav sonunda yapılır)"
            className="mt-4 w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-4 py-2.5 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
          />
        )}
      </div>

      <p className="mt-4 text-xs text-stuhub-text-secondary">
        Sınav modu: cevap sonuca kadar gösterilmez, önceki soruya dönülemez.
      </p>

      <div className="mt-5 flex justify-end">
        <button type="button" onClick={handleNext} disabled={!answered} className="btn-primary">
          {isLast ? 'Sınavı Bitir' : 'Sonraki soru'}
        </button>
      </div>
    </div>
  )
}

export default ExamSimulationPlayer
