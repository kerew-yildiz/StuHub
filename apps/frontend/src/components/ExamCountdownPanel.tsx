import { CalendarBlank, CaretDown, CaretRight, ListChecks, Plus, Trash } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import type { Chapter } from '../api/chapters'
import {
  createExam,
  deleteExam,
  getExamPlan,
  listExams,
  type Exam,
  type ExamPlan,
} from '../api/exams'

export interface ExamCountdownPanelProps {
  courseId: number
  /** Sınav kapsamı seçilebilsin diye dersin bölümleri; boşsa kapsam alanı gizlenir. */
  chapters?: Chapter[]
  /** Verilirse her sınav satırında "Simüle Et" düğmesi görünür (Plan #35). */
  onSimulate?: (exam: Exam) => void
}

const CONTROL_CLASS =
  'rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] focus:border-stuhub-accent'

/** Bugünün yerel ISO tarihi — `<input type="date">` alt sınırı. */
function todayIso(): string {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

/** 'YYYY-MM-DD' → '12 Haziran 2026 Cuma'. */
function formatExamDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    weekday: 'long',
  })
}

/** 'YYYY-MM-DD' → '12 Haz Cuma' (plan günleri için kısa biçim). */
function formatPlanDay(value: string): string {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', weekday: 'short' })
}

function countdownLabel(daysLeft: number): string {
  if (daysLeft < 0) return `${Math.abs(daysLeft)} gün önceydi`
  if (daysLeft === 0) return 'Bugün!'
  if (daysLeft === 1) return 'Yarın'
  return `${daysLeft} gün kaldı`
}

/** Sınav geri sayımı + sınava kadarki günlük çalışma planı (plan #9).
 *
 * Plan sunucuda `srs.compress_to_deadline` ile hesaplanır: vadesi sınavdan sonraya
 * düşen kartlar sınav öncesine çekilir, yük günlere dengeli bölünür. */
export function ExamCountdownPanel({ courseId, chapters = [], onSimulate }: ExamCountdownPanelProps) {
  const [exams, setExams] = useState<Exam[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [title, setTitle] = useState('')
  const [examDate, setExamDate] = useState('')
  const [scope, setScope] = useState<number[]>([])
  const [saving, setSaving] = useState(false)

  const [openExamId, setOpenExamId] = useState<number | null>(null)
  const [plan, setPlan] = useState<ExamPlan | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [planError, setPlanError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void (async () => {
      try {
        const data = await listExams(courseId)
        if (!cancelled) setExams(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Sınavlar alınamadı.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [courseId])

  useEffect(() => {
    if (openExamId === null) {
      setPlan(null)
      return
    }
    let cancelled = false
    setPlanLoading(true)
    setPlanError('')
    void (async () => {
      try {
        const data = await getExamPlan(openExamId)
        if (!cancelled) setPlan(data)
      } catch (err) {
        if (!cancelled) setPlanError(err instanceof Error ? err.message : 'Plan alınamadı.')
      } finally {
        if (!cancelled) setPlanLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [openExamId])

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim() || !examDate || saving) return
    setSaving(true)
    setError('')
    try {
      const created = await createExam(courseId, {
        title: title.trim(),
        exam_date: examDate,
        chapter_ids: scope,
      })
      setExams((current) =>
        [...current, created].sort((a, b) => a.exam_date.localeCompare(b.exam_date) || a.id - b.id),
      )
      setTitle('')
      setExamDate('')
      setScope([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sınav eklenemedi.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(examId: number) {
    setError('')
    try {
      await deleteExam(examId)
      setExams((current) => current.filter((exam) => exam.id !== examId))
      if (openExamId === examId) setOpenExamId(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sınav silinemedi.')
    }
  }

  function toggleScope(chapterId: number) {
    setScope((current) =>
      current.includes(chapterId)
        ? current.filter((id) => id !== chapterId)
        : [...current, chapterId],
    )
  }

  const today = todayIso()

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Sınav Geri Sayımı</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Sınav tarihini gir, tekrar kuyruğun o tarihe sıkıştırılsın. Sınavdan sonraya düşen
        kartlar öne çekilir ve kalan günlere dengeli dağıtılır.
      </p>

      <form onSubmit={handleCreate} className="glass-panel-subtle mt-4 px-4 py-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm text-stuhub-text-secondary">
            Sınav adı
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="Vize"
              className={CONTROL_CLASS}
              aria-label="Sınav adı"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm text-stuhub-text-secondary">
            Sınav tarihi
            <input
              type="date"
              value={examDate}
              min={today}
              onChange={(e) => setExamDate(e.target.value)}
              className={CONTROL_CLASS}
              aria-label="Sınav tarihi"
            />
          </label>

          <button
            type="submit"
            disabled={!title.trim() || !examDate || saving}
            className="btn-primary rounded-control px-4 py-2 text-sm"
          >
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {saving ? 'Ekleniyor…' : 'Sınav ekle'}
          </button>
        </div>

        {chapters.length > 0 && (
          <fieldset className="mt-3 border-0 p-0">
            <legend className="text-xs text-stuhub-text-secondary">
              Kapsam (seçmezsen tüm ders)
            </legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {chapters.map((chapter) => {
                const selected = scope.includes(chapter.id)
                return (
                  <button
                    key={chapter.id}
                    type="button"
                    onClick={() => toggleScope(chapter.id)}
                    aria-pressed={selected}
                    className={`glass-interactive rounded-pill px-3 py-1.5 text-xs font-medium ${
                      selected
                        ? 'border border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
                        : 'glass-panel-subtle border border-transparent text-stuhub-text-secondary'
                    }`}
                  >
                    {chapter.title}
                  </button>
                )
              })}
            </div>
          </fieldset>
        )}
      </form>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
        >
          {error}
        </p>
      )}

      {loading && <p className="mt-4 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}

      {!loading && exams.length === 0 && (
        <div className="glass-panel mt-4 flex items-start gap-3 px-5 py-4">
          <CalendarBlank
            className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-secondary"
            aria-hidden="true"
          />
          <p className="text-sm text-stuhub-text-secondary">
            Henüz sınav eklemedin. Tarihi girdiğin an geri sayım ve günlük çalışma planı burada
            görünür.
          </p>
        </div>
      )}

      {exams.length > 0 && (
        <div className="mt-4 space-y-3">
          {exams.map((exam) => {
            const open = openExamId === exam.id
            const urgent = exam.days_left >= 0 && exam.days_left <= 3
            return (
              <article key={exam.id} className="glass-panel px-5 py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`rounded-pill px-3 py-1 text-sm font-semibold ${
                      exam.days_left < 0
                        ? 'bg-stuhub-glass-2 text-stuhub-text-muted'
                        : urgent
                          ? 'bg-stuhub-error/10 text-stuhub-error'
                          : 'border border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
                    }`}
                  >
                    {countdownLabel(exam.days_left)}
                  </span>
                  <span className="text-sm font-medium">{exam.title}</span>
                  <span className="text-xs text-stuhub-text-secondary">
                    {formatExamDate(exam.exam_date)}
                  </span>
                  <span className="text-xs text-stuhub-text-secondary">
                    {exam.chapter_ids.length === 0
                      ? 'Tüm ders'
                      : `${exam.chapter_ids.length} bölüm kapsamda`}
                  </span>

                  <div className="ml-auto flex items-center gap-2">
                    {onSimulate && (
                      <button
                        type="button"
                        onClick={() => onSimulate(exam)}
                        className="glass-interactive glass-panel-subtle rounded-pill px-3 py-1.5 text-xs font-medium text-stuhub-text-secondary"
                      >
                        Simüle Et
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setOpenExamId(open ? null : exam.id)}
                      aria-expanded={open}
                      className="glass-interactive glass-panel-subtle flex items-center gap-2 rounded-pill px-3 py-1.5 text-xs font-medium text-stuhub-text-secondary"
                    >
                      {open ? (
                        <CaretDown className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <CaretRight className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      Çalışma planı
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(exam.id)}
                      aria-label={`${exam.title} sınavını sil`}
                      className="glass-interactive glass-panel-subtle rounded-pill p-2 text-stuhub-text-secondary"
                    >
                      <Trash className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>

                {open && (
                  <div className="mt-4 border-t border-stuhub-border pt-4">
                    {planLoading && (
                      <p className="text-sm text-stuhub-text-secondary">Plan hesaplanıyor…</p>
                    )}
                    {planError && (
                      <p role="alert" className="text-sm text-stuhub-error">
                        {planError}
                      </p>
                    )}
                    {!planLoading && !planError && plan && plan.days.length === 0 && (
                      <p className="text-sm text-stuhub-text-secondary">
                        {exam.days_left < 0
                          ? 'Sınav tarihi geçmiş — plan oluşturulmadı.'
                          : 'Bu kapsamda planlanacak flashcard yok. Önce kart oluştur.'}
                      </p>
                    )}
                    {!planLoading && !planError && plan && plan.days.length > 0 && (
                      <>
                        <p className="flex items-center gap-2 text-xs text-stuhub-text-secondary">
                          <ListChecks className="h-4 w-4 shrink-0" aria-hidden="true" />
                          {plan.total_cards} kart, {plan.days.length} güne bölündü.
                        </p>
                        <ul className="mt-3 space-y-2">
                          {plan.days.map((day) => (
                            <li
                              key={day.date}
                              className="glass-panel-subtle rounded-control px-4 py-3"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-sm font-medium">
                                  {day.date === today ? 'Bugün' : formatPlanDay(day.date)}
                                </span>
                                <span className="text-xs text-stuhub-text-secondary">
                                  {day.card_count} kart
                                </span>
                              </div>
                              <ul className="mt-2 space-y-1">
                                {day.cards.map((card) => (
                                  <li
                                    key={`${card.set_id}-${card.card_index}`}
                                    className="flex items-start gap-2 text-xs text-stuhub-text-secondary"
                                  >
                                    <span className="rounded-pill bg-stuhub-glass-2 px-2 py-0.5 text-stuhub-text">
                                      {card.topic}
                                    </span>
                                    <span className="pt-0.5">{card.front}</span>
                                  </li>
                                ))}
                              </ul>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

export default ExamCountdownPanel
