import { ArrowClockwise, CheckCircle, Pause, Play, Timer, XCircle } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'

import { answerFeed, fetchFeed, type FeedQuestion } from '../api/feed'
import { createStudySession } from '../api/studySessions'

export interface StudyTimerProps {
  courseId: number
}

const WORK_SECONDS = 25 * 60
const BREAK_SECONDS = 5 * 60
const QUIZ_SIZE = 3

type Phase = 'idle' | 'work' | 'break' | 'quiz' | 'done'

function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

/** 25/5 pomodoro zamanlayıcı — oturum bitince mevcut soru havuzundan (yeni üretim
 * YOK, `fetchFeed`) 3 soruluk mini test gösterir (Plan #14). */
export function StudyTimer({ courseId }: StudyTimerProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [secondsLeft, setSecondsLeft] = useState(WORK_SECONDS)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [questions, setQuestions] = useState<FeedQuestion[]>([])
  const [quizIndex, setQuizIndex] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [correctIndex, setCorrectIndex] = useState<number | null>(null)

  const sessionIdRef = useRef<string>('')
  const elapsedRef = useRef(0)

  useEffect(() => {
    if (!running) return
    const id = window.setInterval(() => {
      elapsedRef.current += 1
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => window.clearInterval(id)
  }, [running])

  useEffect(() => {
    if (secondsLeft > 0) return
    if (phase === 'work') {
      setPhase('break')
      setSecondsLeft(BREAK_SECONDS)
    } else if (phase === 'break') {
      setRunning(false)
      void finishSession()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- finishSession kasıtlı: yalnızca faz geçişinde çağrılır
  }, [secondsLeft, phase])

  const start = () => {
    sessionIdRef.current = crypto.randomUUID()
    elapsedRef.current = 0
    setPhase('work')
    setSecondsLeft(WORK_SECONDS)
    setRunning(true)
    setError('')
  }

  const finishSession = async () => {
    try {
      await createStudySession(courseId, sessionIdRef.current, elapsedRef.current)
      const batch = await fetchFeed(courseId, QUIZ_SIZE)
      const items = batch.items.slice(0, QUIZ_SIZE)
      setQuestions(items)
      setQuizIndex(0)
      setSelected(null)
      setCorrectIndex(null)
      setPhase(items.length > 0 ? 'quiz' : 'done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Oturum kaydedilemedi.')
      setPhase('done')
    }
  }

  const handleAnswer = async (index: number) => {
    const question = questions[quizIndex]
    if (!question || selected !== null) return
    setSelected(index)
    try {
      const result = await answerFeed(question.feed_id, index, 0)
      setCorrectIndex(result.correct_index)
    } catch {
      // sessizce geç — mini test ikincil, oturum zaten kaydedildi
    }
  }

  const nextQuestion = () => {
    if (quizIndex + 1 >= questions.length) {
      setPhase('done')
      return
    }
    setQuizIndex((i) => i + 1)
    setSelected(null)
    setCorrectIndex(null)
  }

  const reset = () => {
    setPhase('idle')
    setRunning(false)
    setSecondsLeft(WORK_SECONDS)
    setQuestions([])
    setError('')
  }

  const activeQuestion = questions[quizIndex]

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center gap-2 text-sm font-semibold text-stuhub-text-secondary">
        <Timer size={18} weight="bold" />
        Çalışma Zamanlayıcı
      </div>

      {phase === 'idle' && (
        <div className="mt-4">
          <button type="button" onClick={start} className="btn-primary">
            25 dakikalık oturumu başlat
          </button>
        </div>
      )}

      {(phase === 'work' || phase === 'break') && (
        <div className="mt-4 flex items-center gap-4">
          <span className="text-4xl font-semibold tabular-nums">{formatClock(secondsLeft)}</span>
          <span className="text-sm text-stuhub-text-secondary">
            {phase === 'work' ? 'Çalışma' : 'Mola'}
          </span>
          <button
            type="button"
            onClick={() => setRunning((r) => !r)}
            className="rounded-control border border-stuhub-border p-2"
            aria-label={running ? 'Duraklat' : 'Devam et'}
          >
            {running ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button
            type="button"
            onClick={reset}
            className="rounded-control border border-stuhub-border p-2"
            aria-label="Sıfırla"
          >
            <ArrowClockwise size={18} />
          </button>
        </div>
      )}

      {phase === 'quiz' && activeQuestion && (
        <div className="mt-5">
          <p className="text-sm text-stuhub-text-secondary">
            Mini test — soru {quizIndex + 1} / {questions.length}
          </p>
          <p className="mt-2 font-medium">{activeQuestion.question}</p>
          <div className="mt-3 space-y-2">
            {activeQuestion.options.map((option, index) => {
              const isSelected = selected === index
              const isCorrect = correctIndex !== null && index === correctIndex
              const isWrong = isSelected && correctIndex !== null && index !== correctIndex
              return (
                <button
                  key={index}
                  type="button"
                  onClick={() => void handleAnswer(index)}
                  disabled={selected !== null}
                  className={`glass-panel-subtle flex w-full items-center justify-between rounded-control px-4 py-2 text-left text-sm ${
                    isCorrect ? 'border border-stuhub-success' : ''
                  } ${isWrong ? 'border border-stuhub-error' : ''}`}
                >
                  <span>{option}</span>
                  {isCorrect && <CheckCircle size={18} className="text-stuhub-success" />}
                  {isWrong && <XCircle size={18} className="text-stuhub-error" />}
                </button>
              )
            })}
          </div>
          {selected !== null && (
            <button type="button" onClick={nextQuestion} className="btn-primary mt-4">
              {quizIndex + 1 >= questions.length ? 'Bitir' : 'Sonraki Soru'}
            </button>
          )}
        </div>
      )}

      {phase === 'done' && (
        <div className="mt-4">
          <p className="text-sm text-stuhub-success">Oturum tamamlandı — harika iş!</p>
          <button type="button" onClick={reset} className="btn-primary mt-3">
            Yeni oturum başlat
          </button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-stuhub-error">{error}</p>}
    </div>
  )
}

export default StudyTimer
