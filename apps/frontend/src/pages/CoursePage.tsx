import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi, type Course } from '../api/courses'
import { materialsApi, type Material } from '../api/materials'
import { ChapterForm } from '../components/ChapterForm'
import { MaterialUploadForm } from '../components/MaterialUploadForm'

type LoadState = 'loading' | 'ready' | 'error'

/** Ders defteri (notebook) landing sayfası — chapter + materyaller (Faz 1.3). */
export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const numericId = Number(courseId)

  const [course, setCourse] = useState<Course | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showChapterForm, setShowChapterForm] = useState(false)

  const load = useCallback(async () => {
    if (!numericId) return
    setState('loading')
    try {
      const [courseData, chapterList, materialList] = await Promise.all([
        coursesApi.get(numericId),
        chaptersApi.listByCourse(numericId),
        materialsApi.listByCourse(numericId),
      ])
      setCourse(courseData)
      setChapters(chapterList)
      setMaterials(materialList)
      setState('ready')
    } catch {
      setState('error')
      setError('Ders yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericId])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreateChapter = async (title: string) => {
    await chaptersApi.create(numericId, title)
    setShowChapterForm(false)
    await load()
  }

  const handleDeleteChapter = async (id: number) => {
    if (!window.confirm('Bu chapter silinecek. Emin misin?')) return
    try {
      await chaptersApi.remove(id)
      setChapters((prev) => prev.filter((c) => c.id !== id))
    } catch {
      setError('Chapter silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleUploadMaterial = async (type: 'textbook' | 'slides', file: File) => {
    await materialsApi.upload(numericId, type, file)
    await load()
  }

  const handleDeleteMaterial = async (id: number) => {
    if (!window.confirm('Bu materyal silinecek. Emin misin?')) return
    try {
      await materialsApi.remove(id)
      setMaterials((prev) => prev.filter((m) => m.id !== id))
    } catch {
      setError('Materyal silinemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section>
      <Link
        to={`/donemler/${course?.term_id ?? ''}`}
        className="text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
      >
        ← Döneme dön
      </Link>
      <div className="mt-2">
        <h1 className="text-3xl font-semibold">{course?.name ?? 'Ders'}</h1>
        {course?.instructor && (
          <p className="mt-1 text-sm text-stuhub-text-secondary">{course.instructor}</p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {state === 'loading' && (
        <p className="mt-8 text-sm text-stuhub-text-secondary">Yükleniyor…</p>
      )}

      {/* Chapter'lar */}
      <div className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Chapter'lar</h2>
          {!showChapterForm && (
            <button
              type="button"
              onClick={() => setShowChapterForm(true)}
              className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
            >
              Yeni Chapter Ekle
            </button>
          )}
        </div>

        {showChapterForm && (
          <div className="mt-4">
            <ChapterForm onSubmit={handleCreateChapter} onCancel={() => setShowChapterForm(false)} />
          </div>
        )}

        <div className="mt-4 space-y-3">
          {chapters.length === 0 && (
            <p className="text-sm text-stuhub-text-secondary">
              Henüz chapter yok. İlk chapter'ını ekleyerek başla.
            </p>
          )}
          {chapters.map((chapter) => (
            <div
              key={chapter.id}
              className="flex items-center justify-between rounded-md border border-stuhub-border bg-stuhub-surface px-5 py-4"
            >
              <Link
                to={`/dersler/${numericId}/defter/${chapter.id}`}
                className="font-medium transition-colors duration-150 hover:text-stuhub-accent"
              >
                {chapter.title}
              </Link>
              <button
                type="button"
                onClick={() => handleDeleteChapter(chapter.id)}
                className="rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                aria-label={`${chapter.title} chapter'ını sil`}
              >
                Sil
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Materyaller */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold">Materyaller</h2>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Ders kitapları (PDF) ve hoca sunumları burada toplanır; AI not ve quiz üretiminde kullanılır.
        </p>
        <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
          <MaterialUploadForm onUpload={handleUploadMaterial} />
          <div className="mt-4 space-y-2">
            {materials.length === 0 && (
              <p className="text-sm text-stuhub-text-secondary">Henüz materyal yok.</p>
            )}
            {materials.map((material) => (
              <div
                key={material.id}
                className="flex items-center justify-between rounded-sm bg-stuhub-bg px-4 py-2 text-sm"
              >
                <span>
                  <span className="font-medium">{material.filepath.split(/[\\/]/).pop()}</span>
                  <span className="ml-2 text-stuhub-text-secondary">
                    {material.type === 'textbook' ? 'Kitap' : 'Sunum'}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => handleDeleteMaterial(material.id)}
                  className="rounded-sm px-2 py-1 text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                  aria-label="Materyali sil"
                >
                  Sil
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
