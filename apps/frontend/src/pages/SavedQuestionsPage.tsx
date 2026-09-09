import { BookmarkSimple, CircleNotch, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { unsaveQuestion } from '../api/feed'
import { listSavedQuestions, type SavedQuestion } from '../api/saved'

type LoadState = 'loading' | 'ready' | 'error'

/** Kaydedilen sorular sayfası — feed'de "kaydet" ile işaretlenmiş sorular, ders/chapter
 * bilgisiyle birlikte. Kayıt kaldırma optimistik: listeden hemen çıkar, sunucu hatasında
 * geri eklenir. */
export function SavedQuestionsPage() {
  const [questions, setQuestions] = useState<SavedQuestion[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [removeError, setRemoveError] = useState('')

  useEffect(() => {
    let cancelled = false
    listSavedQuestions()
      .then((list) => {
        if (!cancelled) {
          setQuestions(list)
          setState('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setState('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleRemove = async (feedId: number) => {
    setRemoveError('')
    const previous = questions
    setQuestions((current) => current.filter((q) => q.feed_id !== feedId))
    try {
      await unsaveQuestion(feedId)
    } catch {
      setQuestions(previous)
      setRemoveError('Kayıt kaldırılamadı. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section>
      <div>
        <h1 className="text-3xl font-semibold">Kaydedilenler</h1>
        <p className="mt-2 text-stuhub-text-secondary">
          Feed'de kaydettiğin sorular burada listelenir.
        </p>
      </div>

      {removeError && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {removeError}
        </p>
      )}

      {state === 'loading' && (
        <p className="mt-8 flex items-center gap-2 text-sm text-stuhub-text-secondary" role="status">
          <CircleNotch size={18} className="animate-spin" />
          Yükleniyor…
        </p>
      )}

      {state === 'error' && (
        <p className="mt-8 flex items-center gap-2 text-sm text-stuhub-error" role="alert">
          <WarningCircle size={18} weight="fill" />
          Kaydedilen sorular alınamadı. Lütfen tekrar deneyin.
        </p>
      )}

      {state === 'ready' && questions.length === 0 && (
        <div className="glass-panel mt-8 flex flex-col items-center gap-2 p-8 text-center">
          <BookmarkSimple size={28} className="text-stuhub-text-secondary" />
          <p className="text-sm text-stuhub-text-secondary">
            Henüz kaydedilmiş soru yok. Quiz akışında bir sorunun yanındaki yer imi ikonuna
            dokunarak kaydedebilirsin.
          </p>
        </div>
      )}

      {state === 'ready' && questions.length > 0 && (
        <div className="mt-6 space-y-4">
          {questions.map((q) => (
            <div key={q.feed_id} className="glass-panel p-6">
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-stuhub-text-secondary">
                  <span className="glass-panel-subtle rounded-pill px-2.5 py-1">
                    {q.course_name} · {q.chapter_title}
                  </span>
                  {q.topic && (
                    <span className="glass-panel-subtle rounded-pill px-2.5 py-1">{q.topic}</span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => void handleRemove(q.feed_id)}
                  aria-label="Kaydı kaldır"
                  className="shrink-0 rounded-control p-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
                >
                  <BookmarkSimple size={20} weight="fill" />
                </button>
              </div>

              <p className="mt-3 text-base font-medium leading-relaxed">{q.question}</p>

              <div className="mt-3 space-y-2">
                {q.options.map((option, index) => (
                  <div
                    key={index}
                    className={`w-full rounded-control border px-4 py-2.5 text-left text-sm ${
                      index === q.correct_index
                        ? 'border-stuhub-success bg-stuhub-success/10 text-stuhub-success'
                        : 'border-stuhub-border text-stuhub-text-secondary'
                    }`}
                  >
                    {option}
                  </div>
                ))}
              </div>

              {q.explanation && (
                <p className="mt-3 rounded-control bg-stuhub-success/10 px-4 py-3 text-sm leading-relaxed text-stuhub-text-secondary">
                  {q.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
