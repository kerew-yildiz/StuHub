import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi } from '../api/courses'
import { downloadAuthed } from '../api/exports'
import { deleteFlashcardSet, listFlashcardSets, type DueCard, type FlashcardSet } from '../api/flashcards'
import { materialsApi } from '../api/materials'
import { deleteNote, exportNotePdf, getNote, listChapterNotes, updateNote, type PdfVariant, type SavedNote } from '../api/notes'
import { slidesApi, type Slide } from '../api/slides'
import { termsApi } from '../api/terms'
import { getTopicProgress, type TopicProgressReport } from '../api/topicProgress'
import { FilePreviewModal } from '../components/FilePreviewModal'
import { ErrorLogPanel } from '../components/ErrorLogPanel'
import { FlashcardPlayer } from '../components/FlashcardPlayer'
import { GuidePanel } from '../components/GuidePanel'
import { ChatPanel } from '../components/ChatPanel'
import { GuideSlidesForm } from '../components/GuideSlidesForm'
import { NoteViewer } from '../components/NoteViewer'
import { ChapterQuizPanel } from '../components/ChapterQuizPanel'
import { SlidePreview } from '../components/SlidePreview'
import { TopicProgressRing } from '../components/TopicProgressRing'
import { SpokenRecallRecorder } from '../components/SpokenRecallRecorder'
import { WorkspaceChrome } from '../components/WorkspaceChrome'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { useAuthedFileUrl } from '../lib/useAuthedFileUrl'
import { confirmDialog } from '../stores/confirmStore'
import { useGenerationStore } from '../stores/generationStore'
import { Pencil, Printer, Monitor, Trash2, X } from 'lucide-react'

type LoadState = 'loading' | 'ready' | 'error'

type NotebookView = 'overview' | 'notes' | 'cards' | 'quiz' | 'recall' | 'guide' | 'ask' | 'mistakes'

/** URL `view` degeri -> aktif gorunum. Gorunum seciminin TEK kaynagi URL'dir; ayri bir
 * "aktif sekme" state'i tutulmaz (state URL ile senkron kalmadiginda iki gorunum ayni
 * anda render ediliyordu: orn. Quiz paneli + Materyale Sor sohbeti). Bilinmeyen/bos
 * deger guvenli varsayilana duser. */
const NOTEBOOK_VIEWS: Record<string, NotebookView> = {
  // Sidebar sozlesmesi (mevcut URL'ler)
  notes: 'notes',
  flashcards: 'cards',
  quiz: 'quiz',
  'material-ask': 'ask',
  mistakes: 'mistakes',
  // Kanonik id'ler — her gorunum URL'den adreslenebilir.
  overview: 'overview',
  cards: 'cards',
  ask: 'ask',
  recall: 'recall',
  guide: 'guide',
}

/** Chapter detay sayfası — guide slides + not + quiz geçmişi (Faz 2/3/4 + iyileştirmeler). */
export function NotebookPage() {
  const { courseId, chapterId } = useParams<{ courseId: string; chapterId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const numericChapterId = Number(chapterId)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [courseName, setCourseName] = useState<string | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [slidesPdfUrl, setSlidesPdfUrl] = useState<string | null>(null)
  const [note, setNote] = useState<SavedNote | null>(null)
  const [noteArchive, setNoteArchive] = useState<SavedNote[]>([])
  const [flashcardSets, setFlashcardSets] = useState<FlashcardSet[]>([])
  const [topicProgress, setTopicProgress] = useState<TopicProgressReport | null>(null)
  const [playingCards, setPlayingCards] = useState<DueCard[] | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [pdfPreview, setPdfPreview] = useState<string | null>(null)
  // Not düzenleme/silme (yönerge §39) — delete confirmation modal'lı.
  const [editingNote, setEditingNote] = useState(false)
  const [pdfMenuOpen, setPdfMenuOpen] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const pdfMenuRef = useRef<HTMLDivElement>(null)
  const [editDraft, setEditDraft] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [noteEditError, setNoteEditError] = useState('')

  // Aktif gorunum TEK kaynaktan turetilir: `view` query parametresi (yoksa/taninmiyorsa
  // guvenli varsayilan 'overview').
  const activeView: NotebookView = NOTEBOOK_VIEWS[searchParams.get('view') ?? ''] ?? 'overview'

  // PDF akordeyonu dış tıklama + Escape ile kapanır.
  useEffect(() => {
    if (!pdfMenuOpen) return
    const onPointerDown = (event: MouseEvent) => {
      if (!pdfMenuRef.current?.contains(event.target as Node)) setPdfMenuOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPdfMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [pdfMenuOpen])
  // Guide slides formu — liste doluysa kapalı, boşsa açık başlar (çoklu sunum)
  const [slidesFormOpen, setSlidesFormOpen] = useState(true)
  const { blobUrl: slidesPdfBlobUrl } = useAuthedFileUrl(slidesPdfUrl)

  // Küresel üretim deposu — sayfa değişse bile üretim sürer (madde 2)
  const noteJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'note' && j.targetId === numericChapterId),
  )
  const flashcardJob = useGenerationStore((s) =>
    s.jobs.find((j) => j.kind === 'flashcards' && j.targetId === numericChapterId),
  )
  const noteProgress = useAnimatedProgress(noteJob?.percent ?? 0)
  const flashcardProgress = useAnimatedProgress(flashcardJob?.percent ?? 0)

  const load = useCallback(async () => {
    if (!numericChapterId) return
    setState('loading')
    try {
      const [chapterData, slideList, existingNote, flashcardSetList] = await Promise.all([
        chaptersApi.get(numericChapterId),
        slidesApi.listByChapter(numericChapterId),
        getNote(numericChapterId),
        listFlashcardSets(numericChapterId),
      ])
      setChapter(chapterData)
      coursesApi
        .get(chapterData.course_id)
        .then((course) => {
          setCourseName(course.name)
          return termsApi.get(course.term_id)
        })
        .then(() => undefined)
        .catch(() => {
          setCourseName(null)
        })
      setSlides(slideList)
      // Liste boşsa yükleme formunu açık, doluysa kapalı tut (çoklu sunum eklenebilir)
      setSlidesFormOpen(slideList.length === 0)
      setNote(existingNote)
      listChapterNotes(numericChapterId)
        .then((archive) => setNoteArchive(archive))
        .catch(() => setNoteArchive(existingNote ? [existingNote] : []))
      setFlashcardSets(flashcardSetList)
      getTopicProgress(numericChapterId)
        .then(setTopicProgress)
        .catch(() => setTopicProgress(null))
      // Slayt materyalinin PDF'i varsa önizleme URL'si hazırla (madde 1)
      const withMaterial = slideList.find((s) => s.material_id != null)
      if (withMaterial?.material_id != null) {
        const material = await materialsApi.get(withMaterial.material_id)
        if (material.file_ext === 'pdf') {
          setSlidesPdfUrl(`/materials/${material.id}/file`)
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
    if (!(await confirmDialog('Bu slide silinecek. Emin misin?'))) return
    try {
      await slidesApi.remove(slideId)
      setSlides((prev) => prev.filter((s) => s.id !== slideId))
    } catch {
      setError('Slide silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleSaveNote = async () => {
    if (!note) return
    setSavingNote(true)
    setNoteEditError('')
    try {
      const updated = await updateNote(note.id, editDraft)
      setNote(updated)
      setEditingNote(false)
      setEditDraft('')
    } catch {
      setNoteEditError('Not kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setSavingNote(false)
    }
  }

  const handleDeleteNote = async () => {
    if (!note) return
    if (!(await confirmDialog('Bu not silinecek. Emin misin?'))) return
    try {
      await deleteNote(note.id)
      setNote(null)
      setEditingNote(false)
      setEditDraft('')
    } catch {
      setError('Not silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleGenerate = async () => {
    const saved = await useGenerationStore
      .getState()
      .generateNote(numericChapterId, chapter?.title ?? 'Chapter')
    if (saved) {
      setNote(saved)
      setNoteArchive((prev) => [saved, ...prev])
      setError('')
      await load()
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
    if (!(await confirmDialog('Bu kart seti silinecek. Emin misin?'))) return
    try {
      await deleteFlashcardSet(setId)
      setFlashcardSets((prev) => prev.filter((s) => s.id !== setId))
    } catch {
      setError('Kart seti silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleDownloadNoteMarkdown = async (noteId: number) => {
    const chapterLabel = (chapter?.title ?? `Chapter ${chapterId}`).trim()
    const ok = await downloadAuthed(`/notes/${noteId}/export?format=md`, `${chapterLabel}.md`)
    if (!ok) setError('Not indirilemedi. Lütfen tekrar deneyin.')
  }

  const handleExportPdf = async (variant: PdfVariant) => {
    if (!note || exportingPdf) return
    setExportingPdf(true)
    try {
      // İndirme adı chapter başlığından: "1. Perspectives Research - Digital Copy.pdf"
      // (kullanıcı isteği; eski "stuhub-not-<id>-<variant>.pdf" yerine).
      const chapterLabel = (chapter?.title ?? `Chapter ${chapterId}`).trim()
      const variantLabel = variant === 'digital' ? 'Digital Copy' : 'Physical Copy'
      await exportNotePdf(note.id, variant, `${chapterLabel} - ${variantLabel}`)
      setPdfMenuOpen(false)
    } catch {
      setError('PDF oluşturulamadı. Lütfen tekrar deneyin.')
    } finally {
      setExportingPdf(false)
    }
  }

  const canGenerate = slides.length > 0
  const generatingNote = noteJob?.status === 'running'
  const generatingFlashcards = flashcardJob?.status === 'running'

  return (
    <section className="page-shell">
      {/* Yönerge §26/§27: workspace chrome — X chapter dashboard'a döner (view parametresi temizlenir) */}
      <WorkspaceChrome exitTo={`/dersler/${courseId}`} exitLabel="Chapter'a dön" />
      <div className="page-header">
        <div>
          <h1 className="page-title">{chapter?.title ?? 'Chapter'}</h1>
          <p className="page-subtitle">{courseName ?? 'Ders'} · çalışma alanı</p>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {state === 'loading' && (
        <p className="mt-8 text-sm text-stuhub-text-secondary">Yükleniyor…</p>
      )}

      {/* TEK gorunum koku — aktif gorunum URL'den turetilir, bloklar birbirini DISLAR.
          `key` geciste eski agacin gercekten unmount olmasini garanti eder;
          `data-view-root` DOM'da kac gorunumun bagli oldugunu olculebilir kilar. */}
      <div key={activeView} data-view-root={activeView}>
        {activeView === 'ask' && (
        <div className="mt-8 workspace-card">
          <p className="eyebrow">MATERYALE SOR</p>
          <p className="mt-1 text-sm text-stuhub-text-secondary">
            Bu chapter'ın notlarına ve materyaline göre soru sor; yanıtlar kaynak atıflı gelir.
          </p>
          <div className="mt-4">
            <ChatPanel courseId={Number(courseId)} />
          </div>
        </div>
        )}

      {/* Sıkıntı #10: Hatalarım artık ayrı workspace view — dashboard'da gömülü panel yok */}
      {activeView === 'mistakes' && (
        <div className="mt-8 workspace-card" data-tour-id="chapter-mistakes">
          <p className="eyebrow">HATALARIM</p>
          <p className="mt-1 text-sm text-stuhub-text-secondary">
            Bu chapter'da quizlerde yanlış cevapladığın sorular.
          </p>
          <div className="mt-4">
            <ErrorLogPanel courseId={Number(courseId)} chapterId={numericChapterId} />
          </div>
        </div>
      )}

      {activeView === 'overview' && (
        <div className="mt-8 space-y-8">
          <div className="glass-panel p-5">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="eyebrow">CHAPTER ÖZETİ</p>
                <h2 className="mt-1 text-xl font-semibold">{chapter?.title ?? 'Chapter'}</h2>
              </div>
              <div className="text-right">
                <p className="eyebrow">ÇALIŞMA SÜRESİ</p>
                <p className="mt-1 text-lg font-semibold">Veri birikiyor</p>
              </div>
            </div>
            <div className="mt-5 thin-progress" aria-hidden="true" data-tour-id="chapter-progress">
              {/* Gerçek tamamlanma: topic bazlı ilerleme (GET /chapters/{id}/topic-progress) —
                  kart tutma + quiz doğruluk sinyalleri. Veri yoksa bar boş kalır. */}
              <span
                style={{
                  width: topicProgress?.total_topics
                    ? `${Math.round((100 * topicProgress.completed_topics) / topicProgress.total_topics)}%`
                    : '0%',
                  opacity: topicProgress?.total_topics ? 1 : 0,
                }}
              />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="glass-panel-subtle rounded-control p-4"><p className="eyebrow">NOT</p><p className="mt-1 text-sm font-medium">{note ? 'Hazır' : 'Henüz yok'}</p></div>
              <div className="glass-panel-subtle rounded-control p-4"><p className="eyebrow">FLASHCARD</p><p className="mt-1 text-sm font-medium">{flashcardSets.reduce((total, set) => total + set.card_count, 0)} kart</p></div>
              <div className="glass-panel-subtle rounded-control p-4"><p className="eyebrow">SON AKTİVİTE</p><p className="mt-1 text-sm font-medium">{note ? 'Not üretimi' : 'Henüz aktivite yok'}</p></div>
            </div>
          </div>

          {/* Sıkıntı: "Eksik konular" kartı gereksizdi — kaldırıldı. Konular artık
              yalnızca aşağıdaki KONULAR listesinde, her satırda ilerleme çemberiyle. */}
          <div className="secondary-grid">
            <button
              type="button"
              className="glass-panel glass-interactive p-5 text-left"
              onClick={() => setSearchParams({ view: 'mistakes' })}
            >
              <p className="eyebrow">HATALARIM</p>
              <p className="mt-2 text-lg font-semibold">Bu chapter için hata geçmişine bak</p>
              <p className="mt-1 text-sm text-stuhub-text-secondary">Chapter'a ait quiz hatalarını ayrı bir sekmede incele.</p>
            </button>
          </div>

          <div data-tour-id="chapter-content">
            <div className="mb-3"><p className="eyebrow">KONULAR</p><h2 className="section-title mt-1">Chapter konuları</h2></div>
            <div className="glass-panel p-2">
              {note?.topics_json?.length ? note.topics_json.map((topic) => {
                const progress = topicProgress?.topics.find(
                  (t) => t.topic.toLowerCase() === topic.topic.toLowerCase(),
                )
                const statusText = progress?.percent == null
                  ? 'Başlamadın'
                  : progress.percent >= 100
                    ? 'Tamamlandı'
                    : `%${Math.round(progress.percent)}`
                return (
                  <div key={topic.topic} className="topic-row">
                    <TopicProgressRing percent={progress?.percent ?? null} />
                    <span className="min-w-0 flex-1 truncate text-sm text-stuhub-text">{topic.topic}</span>
                    <span className="text-xs text-stuhub-text-muted">{statusText}</span>
                  </div>
                )
              }) : (
                <div className="empty-state flex flex-wrap items-center justify-between gap-3 px-3 py-2.5"><span className="min-w-0">Bu chapter için henüz konu özeti oluşmadı.</span><button type="button" className="btn-primary shrink-0" onClick={() => void handleGenerate()} disabled={!canGenerate || generatingNote}>{generatingNote ? 'Üretiliyor…' : 'Not üret'}</button></div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeView === 'notes' && (
        <>
          {/* Kaynak kapsama göstergesi kaldırıldı (kullanıcı kararı: gereksiz/kafa karıştırıcı).
              CoverageIndicator bileşeni hâlâ sonra kullanılmak üzere duruyor. */}

          {/* Guide slides — orijinal dosya önizlemesi (PDF) ya da metin kartı */}
          <div className="mt-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Guide Slides</h2>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              Hocanın sunumu — not üretiminin rehberi. PDF ya da PPTX yükleyebilirsin.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setSlidesFormOpen((v) => !v)}
            aria-expanded={slidesFormOpen}
            className="shrink-0 glass-panel-subtle glass-interactive rounded-control px-3 py-1.5 text-sm font-medium text-stuhub-accent"
          >
            {slidesFormOpen ? 'Gizle' : 'Yeni sunum ekle +'}
          </button>
        </div>

        {slidesFormOpen && (
          <div className="glass-panel mt-4 p-5">
            <GuideSlidesForm onUpload={handleUpload} />
          </div>
        )}

        {slidesPdfUrl ? (
          <div className="glass-panel mt-5 overflow-hidden">
            <div className="flex items-center justify-between border-b border-stuhub-border px-4 py-2">
              <span className="text-sm font-medium">
                Orijinal sunum · {slides.length} slayt
              </span>
              <button
                type="button"
                onClick={() => setPdfPreview(slidesPdfUrl)}
                className="rounded-control bg-stuhub-accent px-3 py-1 text-xs font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
              >
                Tam ekran aç
              </button>
            </div>
            {slidesPdfBlobUrl ? (
              <iframe
                src={slidesPdfBlobUrl}
                title="Sunum önizleme"
                className="h-[65vh] w-full bg-white"
              />
            ) : (
              <p className="flex h-[65vh] w-full items-center justify-center text-sm text-stuhub-text-secondary">
                Yükleniyor…
              </p>
            )}
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
                  onClick={() => { setEditDraft(note.content_md); setEditingNote((v) => !v) }}
                  aria-expanded={editingNote}
                  title="Düzenle"
                  aria-label="Notu düzenle"
                  className="icon-btn"
                >
                  <Pencil size={15} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => void handleDeleteNote()}
                  title="Sil"
                  aria-label="Notu sil"
                  className="icon-btn icon-btn--danger"
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => void handleDownloadNoteMarkdown(note.id)}
                  className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
                >
                  MD İndir
                </button>
                <div className="relative" ref={pdfMenuRef}>
                  <button
                    type="button"
                    onClick={() => setPdfMenuOpen((v) => !v)}
                    aria-expanded={pdfMenuOpen}
                    aria-haspopup="menu"
                    className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
                  >
                    PDF İndir
                  </button>
                  {pdfMenuOpen && (
                    <div
      className="popover-panel right-0 top-[calc(100%+8px)] w-[min(320px,calc(100vw-32px))]"
      role="menu"
      aria-label="PDF kopya türü seç"
                    >
                      <p className="px-3 pb-2 pt-3 text-xs font-medium text-stuhub-text-secondary">
                        Hangi kopya?
                      </p>
                      <button
        type="button"
        role="menuitem"
        onClick={() => void handleExportPdf('physical')}
        disabled={exportingPdf}
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover disabled:opacity-50"
                      >
                        <Printer size={17} className="mt-0.5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">Fiziksel kopya</span>
                          <span className="mt-0.5 block text-xs text-stuhub-text-secondary">
                            Baskı dostu beyaz zemin, siyah logo. Yazıcıdan çıkarın.
                          </span>
                        </span>
                      </button>
                      <button
        type="button"
        role="menuitem"
        onClick={() => void handleExportPdf('digital')}
        disabled={exportingPdf}
        className="flex w-full items-start gap-3 rounded-b-[inherit] px-3 py-2.5 text-left transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover disabled:opacity-50"
                      >
                        <Monitor size={17} className="mt-0.5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">Dijital kopya</span>
                          <span className="mt-0.5 block text-xs text-stuhub-text-secondary">
                            StuHub koyu teması, cam efektli başlık. Ekranda okumak için.
                          </span>
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={generatingNote || !canGenerate}
              className="btn-primary"
              title={canGenerate ? '' : 'Önce guide slides yükle'}
            >
              {generatingNote ? 'Üretiliyor…' : 'Not Oluştur'}
            </button>
          </div>
        </div>

        {generatingNote && (
          <div className="glass-panel mt-4 p-5">
            <p className="text-sm font-medium">{noteJob?.message}</p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-pill bg-stuhub-border">
              <div
                className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
                style={{ width: `${Math.max(noteProgress, 2)}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-stuhub-text-secondary">%{Math.round(noteProgress)} tamamlandı</p>
            {noteJob?.liveContent && (
              <pre className="no-scrollbar mt-4 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-control bg-stuhub-glass-2 p-3 text-sm text-stuhub-text-secondary">
                {noteJob.liveContent}
              </pre>
            )}
          </div>
        )}

        {!generatingNote && note && editingNote && (
          <div className="glass-panel mt-4 space-y-3 p-4">
            <label htmlFor="note-edit-area" className="block text-sm font-medium">Not içeriği (markdown)</label>
            <textarea
              id="note-edit-area"
              value={editDraft}
              onChange={(e) => setEditDraft(e.target.value)}
              rows={14}
              className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] focus:border-stuhub-accent"
            />
            {noteEditError && <p role="alert" className="text-sm text-stuhub-error">{noteEditError}</p>}
            <div className="flex gap-3">
              <button type="button" className="btn-primary" disabled={savingNote} onClick={() => void handleSaveNote()}>
                {savingNote ? 'Kaydediliyor…' : 'Kaydet'}
              </button>
              <button
                type="button"
                className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
                onClick={() => { setEditingNote(false); setEditDraft('') }}
              >
                Vazgeç
              </button>
            </div>
          </div>
        )}

        {!generatingNote && note && !editingNote && (
          <div className="mt-4">
            <NoteViewer note={note} />
            {noteArchive.length > 1 && (
              <div className="mt-4">
                <p className="eyebrow">NOT ARŞİVİ</p>
                <div className="mt-2 flex flex-col gap-2">
                  {noteArchive
                    .filter((n) => n.id !== note.id)
                    .map((archived) => (
                      <button
                        key={archived.id}
                        type="button"
                        onClick={() => setNote(archived)}
                        className="glass-panel-subtle glass-interactive flex items-center justify-between rounded-control px-4 py-3 text-left"
                      >
                        <span className="text-sm font-medium">Eski not — {new Date(archived.generated_at).toLocaleString('tr-TR')}</span>
                        <span className="text-xs text-stuhub-text-secondary">Görüntüle →</span>
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
        {!generatingNote && !note && !error && (
          <p className="mt-4 text-sm text-stuhub-text-secondary">
            Henüz not yok. Guide slides yükleyip “Not Oluştur” ile başla.
          </p>
        )}
          </div>
        </>
      )}

      {activeView === 'cards' && (
        <>
          {/* Flashcard'lar — üretim + çalışma oynatıcısı (Faz V2.2) */}
          <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Kartlar</h2>
          <button
            type="button"
            onClick={() => void handleGenerateFlashcards()}
            disabled={generatingFlashcards || generatingNote || !note}
            className="btn-primary"
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
              <div className="glass-panel mt-4 p-5">
                <p className="text-sm font-medium">{flashcardJob?.message}</p>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-pill bg-stuhub-border">
                  <div
                    className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
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
                  className="glass-panel flex items-center justify-between px-5 py-4"
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
                      onClick={() => handleStudySet(set)}
                      className="rounded-control bg-stuhub-accent px-3 py-1 text-xs font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
                    >
                      Çalış
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteFlashcardSet(set.id)}
                      className="rounded-control p-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10 hover:text-stuhub-error"
                      title="Sil"
                      aria-label="Kart setini sil"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
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

      {activeView === 'quiz' && chapter && <div className="mt-8"><ChapterQuizPanel chapterId={numericChapterId} /></div>}

      {activeView === 'guide' && <GuidePanel scope="chapter" scopeId={numericChapterId} />}

      {activeView === 'recall' && (
        <div className="mt-8">
          <SpokenRecallRecorder chapterId={numericChapterId} />
        </div>
      )}
      </div>

      {/* Sunum onizleme — gorunum degil, ustte acilan modal; gorunum kokunun disinda. */}
      {pdfPreview && (
        <FilePreviewModal
          path={pdfPreview}
          title="Sunum Önizleme"
          onClose={() => setPdfPreview(null)}
        />
      )}
    </section>
  )
}
