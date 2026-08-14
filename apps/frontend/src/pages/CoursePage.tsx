import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi, type Course } from '../api/courses'
import { indexingApi, type IndexingJob } from '../api/indexing'
import { materialsApi, type Material } from '../api/materials'
import { listOverallQuizzes, removeOverallQuiz, type OverallQuiz } from '../api/overall'
import { ChapterForm } from '../components/ChapterForm'
import { FilePreviewModal } from '../components/FilePreviewModal'
import { MaterialUploadForm } from '../components/MaterialUploadForm'
import { OverallQuizPlayer } from '../components/OverallQuizPlayer'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { useGenerationStore } from '../stores/generationStore'

type LoadState = 'loading' | 'ready' | 'error'

/** İndeksleme ilerleme çubuğu — hedefe 1'er birim animasyonla yaklaşır. */
function JobProgressBar({ target }: { target: number }) {
  const progress = useAnimatedProgress(target)
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-stuhub-border">
        <span
          className="block h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
          style={{ width: `${Math.round(progress)}%` }}
        />
      </span>
      <span className="text-stuhub-text-secondary">%{Math.round(progress)}</span>
    </span>
  )
}

/** Ders defteri (notebook) landing sayfası — chapter + materyaller + genel quiz (Faz 1.3/2.2/5). */
export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const numericId = Number(courseId)

  const [course, setCourse] = useState<Course | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [jobs, setJobs] = useState<IndexingJob[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showChapterForm, setShowChapterForm] = useState(false)
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null)

  // genel quiz durumu — küresel üretim deposu (madde 2)
  const [overallQuizzes, setOverallQuizzes] = useState<OverallQuiz[]>([])
  const overallJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'overall' && j.targetId === numericId),
  )
  const quizProgress = useAnimatedProgress(overallJob?.percent ?? 0)
  const [quizKey, setQuizKey] = useState(0)

  const refreshJobs = useCallback(async () => {
    if (!numericId) return
    try {
      const jobList = await indexingApi.listByCourse(numericId)
      setJobs(jobList)
    } catch {
      // iş durumu alınamadıysa sessizce geç (materyal listesi etkilenmesin)
    }
  }, [numericId])

  const load = useCallback(async () => {
    if (!numericId) return
    setState('loading')
    try {
      const [courseData, chapterList, materialList, jobList, quizList] = await Promise.all([
        coursesApi.get(numericId),
        chaptersApi.listByCourse(numericId),
        materialsApi.listByCourse(numericId),
        indexingApi.listByCourse(numericId),
        listOverallQuizzes(numericId),
      ])
      setCourse(courseData)
      setChapters(chapterList)
      setMaterials(materialList)
      setJobs(jobList)
      setOverallQuizzes(quizList)
      setState('ready')
    } catch {
      setState('error')
      setError('Ders yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericId])

  const handleGenerateOverallQuiz = async () => {
    setError('')
    await useGenerationStore
      .getState()
      .generateOverallQuiz(numericId, course?.name ?? 'Ders')
    setQuizKey((k) => k + 1)
    await load()
  }

  const handleDeleteOverallQuiz = async (quizId: number) => {
    if (!window.confirm('Bu genel quiz ve denemeleri silinecek. Emin misin?')) return
    try {
      await removeOverallQuiz(quizId)
      setOverallQuizzes((prev) => prev.filter((q) => q.id !== quizId))
    } catch {
      setError('Genel quiz silinemedi. Lütfen tekrar deneyin.')
    }
  }

  useEffect(() => {
    void load()
  }, [load])

  // İşlenen iş varsa 2 saniyede bir durumu tazele
  const hasActiveJobs = jobs.some((j) => j.status === 'pending' || j.status === 'processing')
  useEffect(() => {
    if (!hasActiveJobs) return
    const id = setInterval(() => void refreshJobs(), 2000)
    return () => clearInterval(id)
  }, [hasActiveJobs, refreshJobs])

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

  const handleIndex = async (materialId: number) => {
    try {
      await indexingApi.enqueue(materialId)
      await refreshJobs()
    } catch {
      setError('İndeksleme başlatılamadı. Lütfen tekrar deneyin.')
    }
  }

  const jobFor = (materialId: number): IndexingJob | undefined =>
    [...jobs].reverse().find((j) => j.material_id === materialId)

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
            {materials.map((material) => {
              const job = jobFor(material.id)
              const active = job && (job.status === 'pending' || job.status === 'processing')
              return (
                <div
                  key={material.id}
                  className="flex items-center justify-between gap-4 rounded-sm bg-stuhub-bg px-4 py-2 text-sm"
                >
                  <span className="min-w-0">
                    <span className="font-medium">{material.display_name}</span>
                    <span className="ml-2 text-stuhub-text-secondary">
                      {material.type === 'textbook' ? 'Kitap' : 'Sunum'}
                      {material.page_count ? ` · ${material.page_count} sayfa` : ''}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    {job?.status === 'done' && (
                      <span className="text-stuhub-success">İndekslendi</span>
                    )}
                    {job?.status === 'failed' && (
                      <span className="text-stuhub-error" title={job.error ?? undefined}>
                        Hata
                      </span>
                    )}
                    {active && <JobProgressBar target={job.progress} />}
                    {!job && (
                      <button
                        type="button"
                        onClick={() => void handleIndex(material.id)}
                        className="rounded-sm bg-stuhub-accent px-3 py-1 text-xs font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
                      >
                        İndeksle
                      </button>
                    )}
                    {job?.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => void handleIndex(material.id)}
                        className="rounded-sm px-3 py-1 text-xs font-medium text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      >
                        Tekrar dene
                      </button>
                    )}
                    {material.filepath.toLowerCase().endsWith('.pdf') && (
                      <button
                        type="button"
                        onClick={() => setPreviewMaterial(material)}
                        className="rounded-sm px-3 py-1 text-xs font-medium text-stuhub-accent transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      >
                        Önizle
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDeleteMaterial(material.id)}
                      className="rounded-sm px-2 py-1 text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      aria-label="Materyali sil"
                    >
                      Sil
                    </button>
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {previewMaterial && (
        <FilePreviewModal
          url={`/api/materials/${previewMaterial.id}/file`}
          title={previewMaterial.display_name}
          onClose={() => setPreviewMaterial(null)}
        />
      )}

      {/* Genel quiz */}
      <div className="mt-12">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Genel Quiz</h2>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              Dersin tüm chapter notlarından 55 soru: çoktan seçmeli, doğru-yanlış, boşluk
              doldurma ve açık uçlu (otomatik puanlama). Tüm quizler kaydedilir.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleGenerateOverallQuiz()}
            disabled={overallJob?.status === 'running'}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
          >
            {overallJob?.status === 'running' ? 'Üretiliyor…' : 'Yeni Genel Quiz Oluştur'}
          </button>
        </div>

        {overallJob?.status === 'running' && (
          <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
            <p className="text-sm font-medium">{overallJob.message}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
              <div
                className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
                style={{ width: `${Math.max(quizProgress, 2)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-stuhub-text-secondary">
              %{Math.round(quizProgress)} tamamlandı
            </p>
          </div>
        )}

        <div className="mt-5 space-y-4">
          {overallQuizzes.length === 0 && overallJob?.status !== 'running' && (
            <p className="text-sm text-stuhub-text-secondary">
              Henüz genel quiz yok. Önce chapter'lar için not oluşturup buradan başlat.
            </p>
          )}
          {overallQuizzes.map((overallQuiz, index) => (
            <details key={overallQuiz.id} open={index === 0}>
              <summary className="flex cursor-pointer items-center justify-between rounded-md border border-stuhub-border bg-stuhub-surface px-5 py-3 font-medium">
                <span>
                  Genel Quiz {overallQuizzes.length - index} ·{' '}
                  {overallQuiz.questions_json.questions.length} soru ·{' '}
                  {overallQuiz.created_at
                    ? new Date(overallQuiz.created_at).toLocaleDateString('tr-TR')
                    : ''}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    void handleDeleteOverallQuiz(overallQuiz.id)
                  }}
                  className="rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                  aria-label="Genel quiz'i sil"
                >
                  Sil
                </button>
              </summary>
              <div className="mt-3">
                <OverallQuizPlayer
                  key={`${overallQuiz.id}-${quizKey}`}
                  quiz={overallQuiz}
                  onDelete={(id) => void handleDeleteOverallQuiz(id)}
                />
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}
