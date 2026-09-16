import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import { AddContentCard } from '../components/AddContentCard'
import { BookOpen, ChevronRight } from 'lucide-react'

interface CourseRow extends Course {
  termName: string
}

export function GlobalCoursesPage() {
  const [rows, setRows] = useState<CourseRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        const terms = await termsApi.list()
        const grouped = await Promise.all(terms.map(async (term: Term) => {
          const courses = await coursesApi.listByTerm(term.id).catch(() => [])
          return courses.map((course) => ({ ...course, termName: term.name }))
        }))
        const flattened = grouped.flat().sort((a, b) => a.name.localeCompare(b.name, 'tr'))
        if (!cancelled) setRows(flattened)
      } catch {
        if (!cancelled) setError('Dersler yüklenemedi. Lütfen tekrar deneyin.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const terms = useMemo(() => [...new Set(rows.map((row) => row.termName))], [rows])

  return (
    <section className="page-shell">
      <header className="page-header">
        <div>
          <h1 className="page-title">Dersler</h1>
          <p className="page-subtitle">Tüm dönemlerindeki derslere tek yerden ulaş.</p>
        </div>
        <div className="glass-panel-subtle flex items-center gap-2 rounded-pill px-3 py-2 text-xs text-stuhub-text-secondary">
          <BookOpen size={15} aria-hidden="true" />
          {terms.length} dönem · {rows.length} ders
        </div>
      </header>

      {error && <p role="alert" className="rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">{error}</p>}
      {loading && <div className="course-grid" aria-busy="true">{Array.from({ length: 6 }, (_, index) => <div key={index} className="glass-panel course-card skeleton-card max-w-[420px]" />)}</div>}
      {!loading && !error && rows.length === 0 && (
        <AddContentCard
          label="Ders ekle"
          description="Henüz ders yok — dersler dönem sayfasında eklenir."
          to="/donemler"
        />
      )}
      {!loading && rows.length > 0 && (
        <div className="course-grid">
          {rows.map((course) => (
            <Link key={course.id} to={`/dersler/${course.id}`} className="glass-panel glass-interactive course-card max-w-[420px]">
              <div className="course-card__head">
                <span className="course-card__term">{course.termName}</span>
                <ChevronRight size={16} aria-hidden="true" />
              </div>
              <div>
                <h2 className="course-card__title">{course.name}</h2>
                {course.instructor && <p className="course-card__meta">{course.instructor}</p>}
              </div>
            </Link>
          ))}
          <AddContentCard
            label="Ders ekle"
            description="Dersler dönem sayfasında eklenir — dönemlerine git."
            to="/donemler"
          />
        </div>
      )}
    </section>
  )
}
