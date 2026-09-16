import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { coursesApi, type Course } from '../api/courses'
import { listExams, type Exam } from '../api/exams'
import { fetchNextAction, type NextAction } from '../api/nextAction'
import { termsApi } from '../api/terms'
import { MonthCalendar } from '../components/MonthCalendar'
import { ArrowRight, Calendar, Crosshair, Trophy } from 'lucide-react'

export type GlobalUtilityKind = 'calendar' | 'exam-plan' | 'study-now'

interface Props {
  kind: GlobalUtilityKind
  termIdOverride?: number
}

function formatExamDate(value: string) {
  const date = new Date(`${value}T12:00:00`)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })
}

export function GlobalUtilityPage({ kind, termIdOverride }: Props) {
  const [searchParams] = useSearchParams()
  const termId = termIdOverride ?? (Number(searchParams.get('termId')) || undefined)
  const [courses, setCourses] = useState<Course[]>([])
  const [exams, setExams] = useState<Array<Exam & { courseName: string }>>([])
  const [actions, setActions] = useState<Array<{ course: Course; action: NextAction | null }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const terms = await termsApi.list()
        const selectedTerms = termId ? terms.filter((term) => term.id === termId) : terms
        const grouped = await Promise.all(selectedTerms.map(async (term) => coursesApi.listByTerm(term.id).catch(() => [])))
        const flat = grouped.flat()
        if (cancelled) return
        setCourses(flat)

        if (kind === 'exam-plan' || kind === 'calendar') {
          const examGroups = await Promise.all(flat.map(async (course) => (await listExams(course.id).catch(() => [])).map((exam) => ({ ...exam, courseName: course.name }))))
          if (!cancelled) setExams(examGroups.flat().sort((a, b) => a.exam_date.localeCompare(b.exam_date)))
        }

        if (kind === 'study-now') {
          const resolved = await Promise.all(flat.map(async (course) => ({ course, action: await fetchNextAction(course.id).catch(() => null) })))
          if (!cancelled) setActions(resolved)
        }
      } catch {
        if (!cancelled) setError('İçerik yüklenemedi. Lütfen tekrar deneyin.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [kind, termId])

  const title = kind === 'calendar' ? 'Takvim' : kind === 'exam-plan' ? 'Sınav Planı' : 'Bugün Ne Çalışsam?'
  const Icon = kind === 'calendar' ? Calendar : kind === 'exam-plan' ? Trophy : Crosshair
  const subtitle = termId ? 'Seçili dönem bağlamındaki planı gösteriyor.' : 'Tüm derslerindeki güncel çalışma bağlamın.'
  const visibleExams = useMemo(() => exams.filter((exam) => exam.days_left >= 0).slice(0, 20), [exams])
  const visibleActions = useMemo(() => actions.filter((item) => item.action && item.action.action !== 'none').slice(0, 12), [actions])

  return (
    <section className="page-shell">
      <header className="page-header">
        <div className="flex items-start gap-3">
          <div className="glass-panel-subtle rounded-control p-2.5"><Icon size={20} aria-hidden="true" /></div>
          <div><h1 className="page-title">{title}</h1><p className="page-subtitle">{subtitle}</p></div>
        </div>
      </header>

      {error && <p role="alert" className="rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">{error}</p>}
      {loading && <div className="list-stack" aria-busy="true">{Array.from({ length: 4 }, (_, index) => <div key={index} className="glass-panel-subtle h-[76px] skeleton-card" />)}</div>}

      {!loading && !error && kind === 'calendar' && (
        <>
          <MonthCalendar />
          <div className="list-stack mt-6">
            <p className="eyebrow">YAKLAŞAN SINAVLAR</p>
          {visibleExams.map((exam) => (
            <article key={exam.id} className="glass-panel list-card">
              <div className="flex min-w-0 items-center gap-3"><Calendar size={18} className="text-stuhub-text-secondary" aria-hidden="true" /><div><p className="font-medium">{exam.title}</p><p className="mt-1 text-xs text-stuhub-text-secondary">{exam.courseName} · {formatExamDate(exam.exam_date)}{exam.days_left === 0 ? ' · bugün' : ` · ${exam.days_left} gün`}</p></div></div>
              <Link to={`/dersler/${exam.course_id}`} className="icon-btn" aria-label={`${exam.courseName} dersine git`}><ArrowRight size={16} aria-hidden="true" /></Link>
            </article>
          ))}
          {visibleExams.length === 0 && <div className="glass-panel-subtle empty-state"><Calendar size={20} aria-hidden="true" /><p>Takvimine henüz etkinlik eklemedin.</p></div>}
          </div>
        </>
      )}

      {!loading && !error && kind === 'exam-plan' && (
        <div className="list-stack">
          {visibleExams.map((exam) => (
            <Link key={exam.id} to={`/dersler/${exam.course_id}?view=exam`} className="glass-panel glass-interactive list-card">
              <div><p className="font-medium">{exam.title}</p><p className="mt-1 text-xs text-stuhub-text-secondary">{exam.courseName} · {formatExamDate(exam.exam_date)}</p></div>
              <span className="text-sm text-stuhub-text-secondary">{exam.days_left === 0 ? 'Bugün' : `${exam.days_left} gün`}</span>
            </Link>
          ))}
          {visibleExams.length === 0 && <div className="glass-panel-subtle empty-state"><Trophy size={20} aria-hidden="true" /><p>Önünde planlanmış sınav bulunmuyor.</p></div>}
        </div>
      )}

      {!loading && !error && kind === 'study-now' && (
        <div className="list-stack">
          {visibleActions.map(({ course, action }) => (
            <Link key={course.id} to={`/dersler/${course.id}`} className="glass-panel glass-interactive list-card">
              <div><p className="font-medium">{course.name}</p><p className="mt-1 text-xs text-stuhub-text-secondary">{action?.reason}</p></div>
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
          ))}
          {visibleActions.length === 0 && <div className="glass-panel-subtle empty-state"><Crosshair size={20} aria-hidden="true" /><p>Şu an için önerilecek bir çalışma adımı yok.</p></div>}
        </div>
      )}

      {!loading && kind !== 'study-now' && courses.length > 0 && (
        <p className="mt-5 text-xs text-stuhub-text-muted">{courses.length} ders tarandı.</p>
      )}
    </section>
  )
}
