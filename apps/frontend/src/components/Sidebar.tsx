import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'

/** Aktif rota vurgusu — tam eşleşme ya da ön ek eşleşmesi. */
function linkClass(active: boolean): string {
  return `glass-interactive block rounded-control border px-3 py-1.5 text-sm font-medium ${
    active
      ? 'border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
      : 'border-transparent text-stuhub-text-secondary hover:text-stuhub-text'
  }`
}

/** Sol dikey sidebar — Dönem → Ders → Chapter ağacı (tembel yükleme). */
export function Sidebar() {
  const location = useLocation()
  const [terms, setTerms] = useState<Term[]>([])
  const [expandedTerms, setExpandedTerms] = useState<Set<number>>(new Set())
  const [coursesByTerm, setCoursesByTerm] = useState<Record<number, Course[]>>({})
  const [expandedCourses, setExpandedCourses] = useState<Set<number>>(new Set())
  const [chaptersByCourse, setChaptersByCourse] = useState<Record<number, Chapter[]>>({})

  useEffect(() => {
    let cancelled = false
    termsApi
      .list()
      .then((list) => {
        if (!cancelled) setTerms(list)
      })
      .catch(() => {
        // Dönem listesi alınamadıysa ağaç boş kalır.
      })
    return () => {
      cancelled = true
    }
  }, [])

  const toggleTerm = async (termId: number) => {
    const next = new Set(expandedTerms)
    if (next.has(termId)) {
      next.delete(termId)
      setExpandedTerms(next)
      return
    }
    next.add(termId)
    setExpandedTerms(next)
    if (!coursesByTerm[termId]) {
      try {
        const list = await coursesApi.listByTerm(termId)
        setCoursesByTerm((prev) => ({ ...prev, [termId]: list }))
      } catch {
        // Lazy yükleme başarısız — sessizce geç.
      }
    }
  }

  const toggleCourse = async (courseId: number) => {
    const next = new Set(expandedCourses)
    if (next.has(courseId)) {
      next.delete(courseId)
      setExpandedCourses(next)
      return
    }
    next.add(courseId)
    setExpandedCourses(next)
    if (!chaptersByCourse[courseId]) {
      try {
        const list = await chaptersApi.listByCourse(courseId)
        setChaptersByCourse((prev) => ({ ...prev, [courseId]: list }))
      } catch {
        // Lazy yükleme başarısız — sessizce geç.
      }
    }
  }

  const isTermActive = (termId: number) =>
    location.pathname === `/donemler/${termId}` ||
    location.pathname.startsWith(`/donemler/${termId}/`)
  const isCourseActive = (courseId: number) =>
    location.pathname.startsWith(`/dersler/${courseId}`)
  const isChapterActive = (courseId: number, chapterId: number) =>
    location.pathname === `/dersler/${courseId}/defter/${chapterId}`

  return (
    <>
      {/* Dar ekran — üstte daraltılmış yatay bar */}
      <nav
        aria-label="Ana gezinme"
        className="sticky top-0 z-30 flex items-center gap-1 overflow-x-auto border-b border-stuhub-border bg-stuhub-bg/70 px-4 py-2 backdrop-blur-2xl md:hidden"
      >
        <NavLink to="/" end className={({ isActive }) => linkClass(isActive)}>
          Dönemler
        </NavLink>
        <NavLink to="/kaydedilenler" className={({ isActive }) => linkClass(isActive)}>
          Kaydedilenler
        </NavLink>
        <NavLink to="/ayarlar" className={({ isActive }) => linkClass(isActive)}>
          Ayarlar
        </NavLink>
      </nav>

      {/* Geniş ekran — sol dikey sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-stuhub-border bg-stuhub-bg/70 backdrop-blur-2xl md:flex">
        <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Dönem ağacı">
          <NavLink
            to="/"
            end
            className={({ isActive }) => linkClass(isActive)}
          >
            Dönemler
          </NavLink>
          <NavLink to="/kaydedilenler" className={({ isActive }) => linkClass(isActive)}>
            Kaydedilenler
          </NavLink>

          {terms.map((term) => {
            const expanded = expandedTerms.has(term.id)
            const courses = coursesByTerm[term.id] ?? []
            return (
              <div key={term.id}>
                <div className="flex items-center">
                  <button
                    type="button"
                    onClick={() => void toggleTerm(term.id)}
                    aria-expanded={expanded}
                    aria-label={`${term.name} dönemini ${expanded ? 'daralt' : 'genişlet'}`}
                    className="shrink-0 rounded-control px-1 py-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
                  >
                    {expanded ? '▾' : '▸'}
                  </button>
                  <Link to={`/donemler/${term.id}`} className={linkClass(isTermActive(term.id))}>
                    <span className="block truncate">{term.name}</span>
                  </Link>
                </div>

                {expanded && (
                  <div className="ml-4 space-y-1 border-l border-stuhub-border pl-2">
                    {courses.length === 0 && (
                      <p className="px-3 py-1.5 text-xs text-stuhub-text-secondary">
                        Henüz ders yok
                      </p>
                    )}
                    {courses.map((course) => {
                      const courseExpanded = expandedCourses.has(course.id)
                      const chapters = chaptersByCourse[course.id] ?? []
                      return (
                        <div key={course.id}>
                          <div className="flex items-center">
                            <button
                              type="button"
                              onClick={() => void toggleCourse(course.id)}
                              aria-expanded={courseExpanded}
                              aria-label={`${course.name} dersini ${courseExpanded ? 'daralt' : 'genişlet'}`}
                              className="shrink-0 rounded-control px-1 py-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
                            >
                              {courseExpanded ? '▾' : '▸'}
                            </button>
                            <Link
                              to={`/dersler/${course.id}`}
                              className={linkClass(isCourseActive(course.id))}
                            >
                              <span className="block truncate">{course.name}</span>
                            </Link>
                          </div>

                          {courseExpanded && (
                            <div className="ml-4 space-y-1 border-l border-stuhub-border pl-2">
                              {chapters.length === 0 && (
                                <p className="px-3 py-1.5 text-xs text-stuhub-text-secondary">
                                  Henüz chapter yok
                                </p>
                              )}
                              {chapters.map((chapter) => (
                                <Link
                                  key={chapter.id}
                                  to={`/dersler/${course.id}/defter/${chapter.id}`}
                                  className={linkClass(isChapterActive(course.id, chapter.id))}
                                >
                                  <span className="block truncate">{chapter.title}</span>
                                </Link>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        <div className="border-t border-stuhub-border p-3">
          <NavLink
            to="/ayarlar"
            className={({ isActive }) => linkClass(isActive)}
          >
            Ayarlar
          </NavLink>
        </div>
      </aside>
    </>
  )
}
