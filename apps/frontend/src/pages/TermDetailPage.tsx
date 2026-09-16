import { useCallback, useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import { coursesApi, type Course, type CourseInput } from '../api/courses'
import { downloadAuthed } from '../api/exports'
import { materialsApi } from '../api/materials'
import { termsApi, type Term } from '../api/terms'
import { AddContentCard } from '../components/AddContentCard'
import { CourseForm } from '../components/CourseForm'
import { CourseCard } from '../components/CourseCard'
import { confirmDialog } from '../stores/confirmStore'
import { GlobalUtilityPage, type GlobalUtilityKind } from './GlobalUtilityPage'

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
          className="btn-primary"
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
  const [searchParams] = useSearchParams()
  const utilityView = searchParams.get('view') as GlobalUtilityKind | null
  const numericId = Number(termId)

  const [term, setTerm] = useState<Term | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingCourse, setEditingCourse] = useState<Course | null>(null)
  const [includeFiles, setIncludeFiles] = useState(false)

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

  const handleCreate = async (
    input: CourseInput,
    textbookFile: File,
    syllabusFile: File | null,
  ) => {
    const created = await coursesApi.create(numericId, input)
    try {
      await materialsApi.upload(created.id, 'textbook', textbookFile)
    } catch {
      await coursesApi.remove(created.id)
      throw new Error('Kitap yüklenemedi, ders geri alındı. Lütfen tekrar deneyin.')
    }
    if (syllabusFile) {
      try {
        await materialsApi.upload(created.id, 'syllabus', syllabusFile)
      } catch {
        setError('Ders ve kitap oluşturuldu ama müfredat yüklenemedi. Sonra tekrar deneyebilirsin.')
      }
    }
    setShowForm(false)
    await load()
  }

  const handleUpdate = async (id: number, input: CourseInput) => {
    await coursesApi.update(id, input)
    setEditingCourse(null)
    await load()
  }

  const handleDeleteCourse = async (course: Course) => {
    if (!(await confirmDialog(`"${course.name}" dersi silinecek. Emin misin?`))) return
    try {
      await coursesApi.remove(course.id)
      setCourses((prev) => prev.filter((c) => c.id !== course.id))
    } catch {
      setError('Ders silinemedi. Lütfen tekrar deneyin.')
    }
  }

  /** Arşivi yetkili yoldan indirir: <a href> gezinmesi `Authorization`
   * başlığını taşımadığından SaaS modda 401 alıyordu (K5). */
  const handleDownloadArchive = async () => {
    const ok = await downloadAuthed(
      `/terms/${numericId}/archive?include_files=${includeFiles}`,
      `stuhub-donem-${numericId}.zip`,
    )
    if (!ok) setError('Dönem arşivi indirilemedi. Lütfen tekrar deneyin.')
  }

  if (utilityView === 'calendar' || utilityView === 'exam-plan' || utilityView === 'study-now') {
    return <GlobalUtilityPage kind={utilityView} termIdOverride={numericId} />
  }

  return (
    <section className="page-shell">
      <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
            onClick={() => void handleDownloadArchive()}
            className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          >
            Dönem Arşivi İndir (.zip)
          </button>
          {!showForm && (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="btn-primary"
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

      <div className="mt-8 course-grid" data-tour-id="term-courses">
        {state === 'loading' && (
          <p className="text-sm text-stuhub-text-secondary">Dersler yükleniyor…</p>
        )}
        {state === 'ready' && courses.length === 0 && !showForm && (
          <AddContentCard
            label="Ders ekle"
            description="Henüz ders yok — ilk dersini ekleyerek başla."
            onClick={() => setShowForm(true)}
          />
        )}
        {courses.map((course) => (
          <div key={course.id} className="max-w-[420px] space-y-3">
            <CourseCard
              course={course}
              onEdit={(target) => setEditingCourse(target)}
              onDelete={(target) => void handleDeleteCourse(target)}
            />
            {editingCourse?.id === course.id && (
              <CourseEditForm
                course={course}
                onSubmit={(input) => handleUpdate(course.id, input)}
                onCancel={() => setEditingCourse(null)}
              />
            )}
          </div>
        ))}
        {courses.length > 0 && !showForm && (
          <AddContentCard
            label="Ders ekle"
            description="Yeni bir ders ekle ve kitabını yükle."
            onClick={() => setShowForm(true)}
          />
        )}
      </div>
    </section>
  )
}
