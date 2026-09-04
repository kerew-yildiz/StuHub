import { PencilSimple } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { coursesApi, type Course, type CourseInput } from '../api/courses'
import { downloadFile, termArchiveUrl } from '../api/exports'
import { materialsApi } from '../api/materials'
import { termsApi, type Term } from '../api/terms'
import { CourseForm } from '../components/CourseForm'
import { MaterialUploadForm } from '../components/MaterialUploadForm'
import { PostCreatePrompt } from '../components/PostCreatePrompt'

type LoadState = 'loading' | 'ready' | 'error'

/** Ders düzenleme mini formu — ad + hoca (hafif, mevcut Form'dan bağımsız). */
function CourseEditForm({
  course,
  onSubmit,
  onCancel,
}: {
  course: Course
  onSubmit: (input: CourseInput) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(course.name)
  const [instructor, setInstructor] = useState(course.instructor ?? '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Ders adı boş olamaz.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit({ name: trimmed, instructor: instructor.trim() || null })
    } catch {
      setError('Ders güncellenemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-panel space-y-3 p-4"
    >
      <div>
        <label htmlFor={`course-edit-name-${course.id}`} className="mb-1 block text-sm font-medium">
          Ders adı
        </label>
        <input
          id={`course-edit-name-${course.id}`}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
        />
      </div>
      <div>
        <label
          htmlFor={`course-edit-instructor-${course.id}`}
          className="mb-1 block text-sm font-medium"
        >
          Hoca (isteğe bağlı)
        </label>
        <input
          id={`course-edit-instructor-${course.id}`}
          type="text"
          value={instructor}
          onChange={(e) => setInstructor(e.target.value)}
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
        />
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
        >
          {busy ? 'Kaydediliyor…' : 'Kaydet'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
        >
          İptal
        </button>
      </div>
    </form>
  )
}

/** Dönem detay sayfası — ders listesi + yeni ders (Faz 1.2). */
export function TermDetailPage() {
  const { termId } = useParams<{ termId: string }>()
  const navigate = useNavigate()
  const numericId = Number(termId)

  const [term, setTerm] = useState<Term | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingCourse, setEditingCourse] = useState<Course | null>(null)
  const [includeFiles, setIncludeFiles] = useState(false)
  const [newCourse, setNewCourse] = useState<Course | null>(null)

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
    const created = await coursesApi.create(numericId, input)
    setShowForm(false)
    setNewCourse(created)
    await load()
  }

  const handleUpdate = async (id: number, input: CourseInput) => {
    await coursesApi.update(id, input)
    setEditingCourse(null)
    await load()
  }

  return (
    <section>
      <Link
        to="/"
        className="text-sm font-medium text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
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
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-stuhub-text-secondary">
            <input
              type="checkbox"
              checked={includeFiles}
              onChange={(e) => setIncludeFiles(e.target.checked)}
            />
            Materyal dosyalarıyla
          </label>
          <button
            type="button"
            onClick={() => downloadFile(termArchiveUrl(numericId, includeFiles))}
            className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          >
            Dönem Arşivi İndir (.zip)
          </button>
          {!showForm && (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
            >
              Yeni ders
            </button>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
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
          <div className="glass-panel-subtle border-dashed p-12 text-center">
            <p className="font-medium">Henüz ders yok</p>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              İlk dersini ekleyerek başla.
            </p>
          </div>
        )}
        {courses.map((course) => (
          <div key={course.id} className="space-y-3">
            <div
              role="link"
              tabIndex={0}
              onClick={() => navigate(`/dersler/${course.id}`)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  navigate(`/dersler/${course.id}`)
                }
              }}
              className="glass-panel glass-interactive flex cursor-pointer items-center justify-between gap-4 p-6"
            >
              <div className="min-w-0">
                <h2 className="text-lg font-semibold">{course.name}</h2>
                {course.instructor && (
                  <p className="mt-1 text-sm text-stuhub-text-secondary">{course.instructor}</p>
                )}
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setEditingCourse(course)
                }}
                className="shrink-0 rounded-control p-2 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
                title="Düzenle"
                aria-label={`${course.name} dersini düzenle`}
              >
                <PencilSimple className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            {editingCourse?.id === course.id && (
              <CourseEditForm
                course={course}
                onSubmit={(input) => handleUpdate(course.id, input)}
                onCancel={() => setEditingCourse(null)}
              />
            )}
          </div>
        ))}
      </div>

      {newCourse && (
        <PostCreatePrompt
          title="Ders kitabını yükle"
          description={`"${newCourse.name}" eklendi. Şimdi kitap PDF'ini yükleyip indeksleyebilirsin — istersen sonra da yapabilirsin.`}
          onClose={() => setNewCourse(null)}
        >
          <MaterialUploadForm
            fixedType="textbook"
            onUpload={async (type, file) => {
              await materialsApi.upload(newCourse.id, type, file)
              setNewCourse(null)
            }}
          />
        </PostCreatePrompt>
      )}
    </section>
  )
}
