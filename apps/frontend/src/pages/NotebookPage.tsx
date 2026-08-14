import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { downloadFile, flashcardSetExportUrl, noteMarkdownUrl } from '../api/exports'
import { deleteFlashcardSet, listFlashcardSets, type DueCard, type FlashcardSet } from '../api/flashcards'
import { materialsApi } from '../api/materials'
import { exportNotePdf, getNote, type SavedNote } from '../api/notes'
import { listQuizzes, removeQuiz, type Quiz } from '../api/quizzes'
import { slidesApi, type Slide } from '../api/slides'
import { FilePreviewModal } from '../components/FilePreviewModal'
import { FlashcardPlayer } from '../components/FlashcardPlayer'
import { GuidePanel } from '../components/GuidePanel'
import { GuideSlidesForm } from '../components/GuideSlidesForm'
import { NoteViewer } from '../components/NoteViewer'
import { QuizPlayer } from '../components/QuizPlayer'
import { SlidePreview } from '../components/SlidePreview'
import { TabBar } from '../components/TabBar'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { useGenerationStore } from '../stores/generationStore'

type LoadState = 'loading' | 'ready' | 'error'

const NOTEBOOK_TABS = [
  { id: 'notes', label: 'Notlar' },
  { id: 'cards', label: 'Kartlar' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'guide', label: 'Rehber' },
] as const

type NotebookTab = (typeof NOTEBOOK_TABS)[number]['id']

/** Chapter detay sayfası — guide slides + not + quiz geçmişi (Faz 2/3/4 + iyileştirmeler). */
export function NotebookPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>()
  const numericChapterId = Number(chapterId)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [slidesPdfUrl, setSlidesPdfUrl] = useState<string | null>(null)
  const [note, setNote] = useState<SavedNote | null>(null)
  const [quizzes, setQuizzes] = useState<Quiz[]>([])
  const [flashcardSets, setFlashcardSets] = useState<FlashcardSet[]>([])
  const [playingCards, setPlayingCards] = useState<DueCard[] | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [pdfPreview, setPdfPreview] = useState<string | null>(null)
  const [tab, setTab] = useState<NotebookTab>('notes')

  // Küresel üretim deposu — sayfa değişse bile üretim sürer (madde 2)
  const noteJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'note' && j.targetId === numericChapterId),
  )
  const quizJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'quiz' && j.targetId === numericChapterId),
  )
  const flashcardJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'flashcards' && j.targetId === numericChapterId),
  )
  const noteProgress = useAnimatedProgress(noteJob?.percent ?? 0)
  const quizProgress = useAnimatedProgress(quizJob?.percent ?? 0)
  const flashcardProgress = useAnimatedProgress(flashcardJob?.percent ?? 0)

  const load = useCallback(async () => {
    if (!numericChapterId) return
    setState('loading')
    try {
      const [chapterData, slideList, existingNote, quizList, flashcardSetList] = await Promise.all([
        chaptersApi.get(numericChapterId),
        slidesApi.listByChapter(numericChapterId),
        getNote(numericChapterId),
        listQuizzes(numericChapterId),
        listFlashcardSets(numericChapterId),
      ])
      setChapter(chapterData)
      setSlides(slideList)
      setNote(existingNote)
      setQuizzes(quizList)
      setFlashcardSets(flashcardSetList)
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

  const refreshFlashcardSets = async () => {
    if (!numericChapterId) return
    setFlashcardSets(await listFlashcardSets(numericChapterId))
  }

  const handleGenerateFlashcards = async () => {
    const set = await useGenerationStore
      .getState()
      .generateFlashcards(numericChapterId, chapter?.title ?? 'Chapter')
    if (set) {
      setError('')
      await refreshFlashcardSets()
    }
  }

  const handleStudySet = (set: FlashcardSet) => {
    setPlayingCards(
      set.cards_json.map((card, cardIndex) => ({
        set_id: set.id,
        card_index: cardIndex,
        card,
        review: null,
        due: true,
      })),
    )
  }

  const handleDeleteFlashcardSet = async (setId: number) => {
    if (!window.confirm('Bu kart seti silinecek. Emin misin?')) return
    try {
      await deleteFlashcardSet(setId)
      setFlashcardSets((prev) => prev.filter((s) => s.id !== setId))
    } catch {
      setError('Kart seti silinemedi. Lütfen tekrar deneyin.')
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
  const generatingFlashcards = flashcardJob?.status === 'running'

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

      <div className="mt-8">
        <TabBar
          tabs={NOTEBOOK_TABS}
          activeId={tab}
          onSelect={(id) => setTab(id as NotebookTab)}
          ariaLabel="Çalışma modu"
        />
      </div>

      {tab === 'notes' && (
        <>
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
              <>
                <button
                  type="button"
                  onClick={() => downloadFile(noteMarkdownUrl(note.id))}
                  className="rounded-sm border border-stuhub-border bg-stuhub-surface px-4 py-2 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
                >
                  MD İndir
                </button>
                <button
                  type="button"
                  onClick={() => void handleExportPdf()}
                  className="rounded-sm border border-stuhub-border bg-stuhub-surface px-4 py-2 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
                >
                  PDF İndir
                </button>
              </>
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
        </>
      )}

      {tab === 'cards' && (
        <>
          {/* Flashcard'lar — üretim + çalışma oynatıcısı (Faz V2.2) */}
          <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Kartlar</h2>
          <button
            type="button"
            onClick={() => void handleGenerateFlashcards()}
            disabled={generatingFlashcards || generatingNote || !note}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-50"
            title={note ? '' : 'Önce not oluştur'}
          >
            {generatingFlashcards ? 'Üretiliyor…' : 'Kart Oluştur'}
          </button>
        </div>

        {playingCards ? (
          <div className="mt-4">
            <FlashcardPlayer
              dueCards={playingCards}
              onFinished={() => {
                setPlayingCards(null)
                void refreshFlashcardSets()
              }}
              onExit={() => setPlayingCards(null)}
            />
          </div>
        ) : (
          <>
            {generatingFlashcards && (
              <div className="mt-4 rounded-md border border-stuhub-border bg-stuhub-surface p-5">
                <p className="text-sm font-medium">{flashcardJob?.message}</p>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-stuhub-border">
                  <div
                    className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
                    style={{ width: `${Math.max(flashcardProgress, 2)}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-stuhub-text-secondary">
                  %{Math.round(flashcardProgress)} tamamlandı
                </p>
              </div>
            )}

            <div className="mt-5 space-y-4">
              {flashcardSets.length === 0 && !generatingFlashcards && (
                <p className="text-sm text-stuhub-text-secondary">
                  Henüz kart seti yok. Not oluşturup “Kart Oluştur” ile başla.
                </p>
              )}
              {flashcardSets.map((set, setIndex) => (
                <div
                  key={set.id}
                  className="flex items-center justify-between rounded-md border border-stuhub-border bg-stuhub-surface px-5 py-4"
                >
                  <span className="text-sm">
                    <span className="font-medium">
                      Kart Seti {flashcardSets.length - setIndex}
                    </span>
                    <span className="ml-2 text-stuhub-text-secondary">
                      {set.card_count} kart ·{' '}
                      {set.created_at
                        ? new Date(set.created_at).toLocaleDateString('tr-TR')
                        : ''}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <button
                      type="button"
                      onClick={() => downloadFile(flashcardSetExportUrl(set.id, 'apkg'))}
                      className="rounded-sm border border-stuhub-border px-2 py-1 text-xs font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      title="Anki'ye aktar (.apkg)"
                    >
                      Anki
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadFile(flashcardSetExportUrl(set.id, 'csv'))}
                      className="rounded-sm border border-stuhub-border px-2 py-1 text-xs font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      title="CSV indir"
                    >
                      CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => handleStudySet(set)}
                      className="rounded-sm bg-stuhub-accent px-3 py-1 text-xs font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
                    >
                      Çalış
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteFlashcardSet(set.id)}
                      className="rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
                      aria-label="Kart setini sil"
                    >
                      Sil
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
          </div>
        </>
      )}

      {tab === 'quiz' && (
        <>
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
        </>
      )}

      {tab === 'guide' && <GuidePanel scope="chapter" scopeId={numericChapterId} />}

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
