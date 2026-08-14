import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { coursesApi, type Course, type CourseInput } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import { CourseForm } from '../components/CourseForm'

type LoadState = 'loading' | 'ready' | 'error'

/** Dönem detay sayfası — ders listesi + yeni ders (Faz 1.2). */
export function TermDetailPage() {
  const { termId } = useParams<{ termId: string }>()
  const numericId = Number(termId)

  const [term, setTerm] = useState<Term | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    if (!numericId) return
    setState('loading')
    try {
      const [termData, courseList] = await Promise.all([
        termsApi.get(numericId),
        coursesApi.listByTerm(numericId),
      ])
      setTerm(termData)
      setCourses(courseList)
      setState('ready')
    } catch {
      setState('error')
      setError('Dönem yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericId])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreate = async (input: CourseInput) => {
    await coursesApi.create(numericId, input)
    setShowForm(false)
    await load()
  }

  return (
    <section>
      <Link
        to="/"
        className="text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
      >
        ← Dönemler
      </Link>
      <div className="mt-2 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">{term?.name ?? 'Dönem'}</h1>
          <p className="mt-2 text-stuhub-text-secondary">
            Derslerini buradan yönetebilirsin.
          </p>
        </div>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
          >
            Yeni ders
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {showForm && (
        <div className="mt-6">
          <CourseForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      <div className="mt-8 space-y-4">
        {state === 'loading' && (
          <p className="text-sm text-stuhub-text-secondary">Dersler yükleniyor…</p>
        )}
        {state === 'ready' && courses.length === 0 && (
          <div className="rounded-md border border-dashed border-stuhub-border bg-stuhub-surface p-12 text-center">
            <p className="font-medium">Henüz ders yok</p>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              İlk dersini ekleyerek başla.
            </p>
          </div>
        )}
        {courses.map((course) => (
          <Link
            key={course.id}
            to={`/dersler/${course.id}`}
            className="block rounded-md border border-stuhub-border bg-stuhub-surface p-6 transition-colors duration-150 hover:bg-stuhub-surface-hover"
          >
            <h2 className="text-lg font-semibold">{course.name}</h2>
            {course.instructor && (
              <p className="mt-1 text-sm text-stuhub-text-secondary">{course.instructor}</p>
            )}
          </Link>
        ))}
      </div>
    </section>
  )
}
