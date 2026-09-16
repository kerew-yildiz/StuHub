import { useCallback, useEffect, useState } from 'react'

import { listChapterQuizzes, generateChapterQuiz, submitChapterQuiz, type ChapterQuiz } from '../api/chapterQuizzes'
import { alertDialog } from '../stores/alertStore'
import { Plus, ArrowRight, Check, CircleAlert, LoaderCircle } from 'lucide-react'

interface Props {
  chapterId: number
}

export function ChapterQuizPanel({ chapterId }: Props) {
  const [quizzes, setQuizzes] = useState<ChapterQuiz[]>([])
  const [selectedQuiz, setSelectedQuiz] = useState<ChapterQuiz | null>(null)
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<Awaited<ReturnType<typeof submitChapterQuiz>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listChapterQuizzes(chapterId)
      setQuizzes(data)
      setSelectedQuiz(null)
      setResult(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Quizler yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [chapterId])

  const handleCreate = async () => {
    if (creating) return
    setCreating(true)
    try {
      await generateChapterQuiz(chapterId)
      await load()
    } catch (err) {
      void alertDialog(err instanceof Error ? err.message : 'Quiz üretilemedi.')
    } finally {
      setCreating(false)
    }
  }

  useEffect(() => { void load() }, [load])

  if (loading) return <div className="glass-panel workspace-card p-8"><div className="skeleton-card h-5 w-48" /><div className="skeleton-card mt-6 h-24 w-full" /></div>
  if (error) return <div className="glass-panel workspace-card p-8"><div className="flex items-center gap-3 text-stuhub-error"><CircleAlert size={20} aria-hidden="true" /><p>{error}</p></div></div>

  if (!selectedQuiz) return (
    <div className="workspace-card">
      <div className="mb-5">
        <p className="eyebrow">QUIZLER</p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">Chapter için hazırlanmış quizleri seç ve çöz.</p>
      </div>
      <div className="list-stack">
        {quizzes.map((quiz, quizIndex) => (
          <button key={quiz.id} type="button" className="glass-panel glass-interactive list-card text-left" onClick={() => { setSelectedQuiz(quiz); setIndex(0); setAnswers({}); setResult(null) }}>
            <div><p className="font-medium">Quiz {quizzes.length - quizIndex}</p><p className="mt-1 text-xs text-stuhub-text-secondary">{quiz.questions.length} soru · {new Date(quiz.created_at).toLocaleDateString('tr-TR')}</p></div>
            <ArrowRight size={17} aria-hidden="true" />
          </button>
        ))}
        {quizzes.length === 0 && <div className="glass-panel-subtle empty-state"><Check size={20} aria-hidden="true" /><p>Henüz bu chapter için oluşturulmuş quiz yok.</p></div>}
        <button
          type="button"
          className="glass-panel glass-interactive list-card text-left"
          onClick={() => void handleCreate()}
          disabled={creating}
        >
          <div>
            <p className="font-medium">{creating ? 'Quiz oluşturuluyor…' : 'Quiz Oluştur'}</p>
            <p className="mt-1 text-xs text-stuhub-text-secondary">{creating ? 'Notlardan yeni sorular üretiliyor.' : 'Chapter notlarından yeni bir quiz üret.'}</p>
          </div>
          {creating ? <LoaderCircle size={17} className="animate-spin" aria-hidden="true" /> : <Plus size={17} aria-hidden="true" />}
        </button>
      </div>
    </div>
  )

  if (result) return (
    <div className="workspace-card">
      <div className="glass-panel p-8">
        <Check size={28} aria-hidden="true" />
        <p className="eyebrow mt-4">QUIZ SONUCU</p>
        <h2 className="mt-1 text-2xl font-semibold">%{Math.round(result.score)} doğru</h2>
        <div className="mt-6 list-stack">
          {result.results.map((item) => (
            <article key={item.qid} className="glass-panel-subtle rounded-control p-4">
              <p className="text-sm font-medium leading-6">{item.question}</p>
              <p className={`mt-2 text-sm ${item.correct ? 'text-stuhub-success' : 'text-stuhub-error'}`}>{item.correct ? 'Doğru' : 'Yanlış'}</p>
              {item.explanation && <p className="mt-1 text-sm leading-6 text-stuhub-text-secondary">{item.explanation}</p>}
            </article>
          ))}
        </div>
        <button type="button" className="btn-primary mt-6" onClick={() => { setSelectedQuiz(null); setResult(null) }}>Quiz listesine dön <ArrowRight size={16} aria-hidden="true" /></button>
      </div>
    </div>
  )

  const question = selectedQuiz.questions[index]
  if (!question) return null
  const selected = answers[question.qid]
  const answeredCount = Object.keys(answers).length
  const progress = selectedQuiz.questions.length ? answeredCount / selectedQuiz.questions.length * 100 : 0
  const next = index + 1 >= selectedQuiz.questions.length

  const submit = async () => {
    if (selected === undefined || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const response = await submitChapterQuiz(selectedQuiz.id, Object.entries(answers).map(([qid, selected_index]) => ({ qid, selected_index })))
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Quiz değerlendirilemedi.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="workspace-card">
      <div className="mb-4 flex items-center justify-between">
        <div><p className="eyebrow">QUIZ</p><p className="mt-1 text-sm text-stuhub-text-secondary">Soru {index + 1} / {selectedQuiz.questions.length}</p></div>
        <span className="text-xs text-stuhub-text-muted">%{Math.round(progress)}</span>
      </div>
      <div className="thin-progress mb-7"><span style={{ width: `${Math.max(progress, 4)}%` }} /></div>
      {error && <p role="alert" className="mb-4 rounded-control bg-stuhub-error/10 px-4 py-3 text-sm text-stuhub-error">{error}</p>}
      <article className="glass-panel p-6 sm:p-8">
        {question.topic && <p className="eyebrow">{question.topic}</p>}
        <h2 className="mt-3 text-xl font-semibold leading-8">{question.question}</h2>
        <div className="mt-7 grid gap-3">
          {question.options.map((option, optionIndex) => (
            <button key={`${question.qid}-${optionIndex}`} type="button" className={`rounded-control border px-4 py-3 text-left text-sm transition-[background,border-color,transform] duration-[var(--duration-micro)] ${selected === optionIndex ? 'border-stuhub-border-strong bg-stuhub-accent-glass text-stuhub-text' : 'border-stuhub-border bg-stuhub-glass-2 text-stuhub-text-secondary hover:border-stuhub-border-strong hover:bg-stuhub-glass-2-hover'}`} onClick={() => setAnswers((prev) => ({ ...prev, [question.qid]: optionIndex }))}>
              <span className="mr-3 text-xs font-semibold text-stuhub-text-muted">{String.fromCharCode(65 + optionIndex)}</span>{option}
            </button>
          ))}
        </div>
        <div className="mt-7 flex justify-end gap-3">
          {index > 0 && <button type="button" className="glass-panel-subtle rounded-control px-4 py-2 text-sm text-stuhub-text-secondary" onClick={() => setIndex((value) => value - 1)}>Önceki</button>}
          {!next ? <button type="button" className="btn-primary" disabled={selected === undefined} onClick={() => setIndex((value) => value + 1)}>Sonraki <ArrowRight size={16} aria-hidden="true" /></button> : <button type="button" className="btn-primary" disabled={selected === undefined || submitting} onClick={() => void submit()}>{submitting ? 'Değerlendiriliyor…' : 'Quiz’i Bitir'} <ArrowRight size={16} aria-hidden="true" /></button>}
        </div>
      </article>
    </div>
  )
}
