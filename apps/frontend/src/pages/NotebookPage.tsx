import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { materialsApi } from '../api/materials'
import { exportNotePdf, getNote, type SavedNote } from '../api/notes'
import { listQuizzes, removeQuiz, type Quiz } from '../api/quizzes'
import { slidesApi, type Slide } from '../api/slides'
import { FilePreviewModal } from '../components/FilePreviewModal'
import { GuideSlidesForm } from '../components/GuideSlidesForm'
import { NoteViewer } from '../components/NoteViewer'
import { QuizPlayer } from '../components/QuizPlayer'
import { SlidePreview } from '../components/SlidePreview'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { useGenerationStore } from '../stores/generationStore'

type LoadState = 'loading' | 'ready' | 'error'

/** Chapter detay sayfası — guide slides + not + quiz geçmişi (Faz 2/3/4 + iyileştirmeler). */
export function NotebookPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>()
  const numericChapterId = Number(chapterId)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [slidesPdfUrl, setSlidesPdfUrl] = useState<string | null>(null)
  const [note, setNote] = useState<SavedNote | null>(null)
  const [quizzes, setQuizzes] = useState<Quiz[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [pdfPreview, setPdfPreview] = useState<string | null>(null)

  // Küresel üretim deposu — sayfa değişse bile üretim sürer (madde 2)
  const noteJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'note' && j.targetId === numericChapterId),
  )
  const quizJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'quiz' && j.targetId === numericChapterId),
  )
  const noteProgress = useAnimatedProgress(noteJob?.percent ?? 0)
  const quizProgress = useAnimatedProgress(quizJob?.percent ?? 0)

  const load = useCallback(async () => {
    if (!numericChapterId) return
    setState('loading')
    try {
      const [chapterData, slideList, existingNote, quizList] = await Promise.all([
        chaptersApi.get(numericChapterId),
        slidesApi.listByChapter(numericChapterId),
        getNote(numericChapterId),
        listQuizzes(numericChapterId),
      ])
      setChapter(chapterData)
      setSlides(slideList)
      setNote(existingNote)
      setQuizzes(quizList)
      // Slayt materyalinin PDF'i varsa önizleme URL'si hazırla (madde 1)
      const withMaterial = slideList.find((s) => s.material_id != null)
      if (withMaterial?.material_id != null) {
        const material = await materialsApi.get(withMaterial.material_id)
        if (material.filepath.toLowerCase().endsWith('.pdf')) {
          setSlidesPdfUrl(`/api/materials/${material.id}/file`)
        } else {
          setSlidesPdfUrl(null)
        }
      } else {
        setSlidesPdfUrl(null)
      }
      setState('ready')
    } catch {
      setState('error')
      setError('Chapter yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericChapterId])

  useEffect(() => {
    void load()
  }, [load])

  const handleUpload = async (file: File) => {
    await slidesApi.upload(numericChapterId, file)
    await load()
  }

  const handleDeleteSlide = async (slideId: number) => {
    if (!window.confirm('Bu slide silinecek. Emin misin?')) return
    try {
      await slidesApi.remove(slideId)
      setSlides((prev) => prev.filter((s) => s.id !== slideId))
    } catch {
      setError('Slide silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleGenerate = async () => {
    const saved = await useGenerationStore
      .getState()
      .generateNote(numericChapterId, chapter?.title ?? 'Chapter')
    if (saved) {
      setNote(saved)
      setError('')
      // Madde 5: quiz not bittikten sonra OTOMATİK üretilir
      await useGenerationStore.getState().generateQuiz(numericChapterId, chapter?.title ?? 'Chapter')
      await load()
    }
  }

  const handleGenerateQuiz = async () => {
    await useGenerationStore
      .getState()
      .generateQuiz(numericChapterId, chapter?.title ?? 'Chapter')
    await load()
  }

  const handleDeleteQuiz = async (quizId: number) => {
    if (!window.confirm('Bu quiz ve denemeleri silinecek. Emin misin?')) return
    try {
      await removeQuiz(quizId)
      setQuizzes((prev) => prev.filter((q) => q.id !== quizId))
    } catch {
      setError('Quiz silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleExportPdf = async () => {
    if (!note) return
    try {
      await exportNotePdf(note.id)
    } catch {
      setError('PDF oluşturulamadı. Lütfen tekrar deneyin.')
    }
  }

  const canGenerate = slides.length > 0
  const generatingNote = noteJob?.status === 'running'
  const generatingQuiz = quizJob?.status === 'running'

  return (
    <section>
      <Link
        to={`/dersler/${courseId ?? ''}`}
        className="text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
      >
        ← Derse dön
      </Link>
      <div className="mt-2">
        <h1 className="text-3xl font-semibold">{chapter?.title ?? 'Chapter'}</h1>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {state === 'loading' && (
        <p className="mt-8 text-sm text-stuhub-text-secondary">Yükleniyor…</p>
      )}

      {/* Guide slides — orijinal dosya önizlemesi (PDF) ya da metin kartı */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold">Guide Slides</h2>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Hocanın sunumu — not üretiminin rehberi. PDF ya da PPTX yükleyebilirsin.
        </p>
        <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
          <GuideSlidesForm onUpload={handleUpload} />
        </div>

        {slidesPdfUrl ? (
          <div className="mt-5 overflow-hidden rounded-md border border-stuhub-border bg-stuhub-surface">
            <div className="flex items-center justify-between border-b border-stuhub-border bg-stuhub-bg px-4 py-2">
              <span className="text-sm font-medium">
                Orijinal sunum · {slides.length} slayt
              </span>
              <button
                type="button"
                onClick={() => setPdfPreview(slidesPdfUrl)}
                className="rounded-sm bg-stuhub-accent px-3 py-1 text-xs font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
              >
                Tam ekran aç
              </button>
            </div>
            <iframe
              src={slidesPdfUrl}
              title="Sunum önizleme"
              className="h-[65vh] w-full bg-white"
            />
          </div>
        ) : (
          <div className="mt-5">
            <SlidePreview slides={slides} onDelete={handleDeleteSlide} />
          </div>
        )}
      </div>

      {/* Not — açılır kapanır pencere + PDF indir */}
      <div className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Not</h2>
          <div className="flex gap-3">
            {note && !generatingNote && (
              <button
                type="button"
                onClick={() => void handleExportPdf()}
                className="rounded-sm border border-stuhub-border bg-stuhub-surface px-4 py-2 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
              >
                PDF İndir
              </button>
            )}
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={generatingNote || !canGenerate}
              className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
              title={canGenerate ? '' : 'Önce guide slides yükle'}
            >
              {generatingNote ? 'Üretiliyor…' : 'Not Oluştur'}
            </button>
          </div>
        </div>

        {generatingNote && (
          <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
            <p className="text-sm font-medium">{noteJob?.message}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
              <div
                className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
                style={{ width: `${Math.max(noteProgress, 2)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-stuhub-text-secondary">%{Math.round(noteProgress)} tamamlandı</p>
            {noteJob?.liveContent && (
              <pre className="mt-4 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-sm bg-stuhub-bg p-3 text-sm text-stuhub-text-secondary">
                {noteJob.liveContent}
              </pre>
            )}
          </div>
        )}

        {!generatingNote && note && (
          <details open className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface">
            <summary className="cursor-pointer select-none px-5 py-3 font-medium">
              Not görüntüle / gizle
            </summary>
            <div className="border-t border-stuhub-border px-6 py-5">
              <NoteViewer note={note} />
            </div>
          </details>
        )}
        {!generatingNote && !note && !error && (
          <p className="mt-4 text-sm text-stuhub-text-secondary">
            Henüz not yok. Guide slides yükleyip “Not Oluştur” ile başla.
          </p>
        )}
      </div>

      {/* Bölüm quizleri — geçmiş korunur, hepsi listelenir (madde 3) */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Quizler</h2>
          <button
            type="button"
            onClick={() => void handleGenerateQuiz()}
            disabled={generatingQuiz || generatingNote || !note}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
            title={note ? '' : 'Önce not oluştur'}
          >
            {generatingQuiz ? 'Üretiliyor…' : 'Yeni Quiz Oluştur'}
          </button>
        </div>

        {generatingQuiz && (
          <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
            <p className="text-sm font-medium">{quizJob?.message}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
              <div
                className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
                style={{ width: `${Math.max(quizProgress, 2)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-stuhub-text-secondary">%{Math.round(quizProgress)} tamamlandı</p>
          </div>
        )}

        <div className="mt-5 space-y-4">
          {quizzes.length === 0 && !generatingQuiz && (
            <p className="text-sm text-stuhub-text-secondary">
              Henüz quiz yok. Not oluşturunca otomatik hazırlanır.
            </p>
          )}
          {quizzes.map((quiz, index) => (
            <details key={quiz.id} open={index === 0}>
              <summary className="flex cursor-pointer items-center justify-between rounded-md border border-stuhub-border bg-stuhub-surface px-5 py-3 font-medium">
                <span>
                  Quiz {quizzes.length - index} ·{' '}
                  {quiz.questions_json.topics.reduce(
                    (n, t) => n + t.questions.length,
                    0,
                  )}{' '}
                  soru ·{' '}
                  {quiz.created_at ? new Date(quiz.created_at).toLocaleDateString('tr-TR') : ''}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    void handleDeleteQuiz(quiz.id)
                  }}
                  className="rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                  aria-label="Quiz'i sil"
                >
                  Sil
                </button>
              </summary>
              <div className="mt-3">
                <QuizPlayer
                  key={quiz.id}
                  quiz={quiz}
                  onDelete={(id) => void handleDeleteQuiz(id)}
                />
              </div>
            </details>
          ))}
        </div>
      </div>

      {pdfPreview && (
        <FilePreviewModal
          url={pdfPreview}
          title="Sunum Önizleme"
          onClose={() => setPdfPreview(null)}
        />
      )}
    </section>
  )
}
