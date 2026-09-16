import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi, type Course } from '../api/courses'
import { downloadAuthed, type FlashcardExportFormat } from '../api/exports'
import { fetchDueCards, listCourseFlashcardSets, type DueCard, type FlashcardSet } from '../api/flashcards'
import { indexingApi, type IndexingJob } from '../api/indexing'
import { materialsApi, type Material } from '../api/materials'
import { type OverallOutcome } from '../api/overall'
import { slidesApi } from '../api/slides'
import { AbandonedTopicsList } from '../components/AbandonedTopicsList'
import { AddContentCard } from '../components/AddContentCard'
import { ChapterForm } from '../components/ChapterForm'
import { ChatPanel } from '../components/ChatPanel'
import { ComparisonTable } from '../components/ComparisonTable'
import { ErrorLogPanel } from '../components/ErrorLogPanel'
import { EssayDraftCoach } from '../components/EssayDraftCoach'
import { EssayGraderForm } from '../components/EssayGraderForm'
import { ExamCountdownPanel } from '../components/ExamCountdownPanel'
import { ExamPostmortemForm, type MissedQuestion } from '../components/ExamPostmortemForm'
import { ExamSimulationPlayer } from '../components/ExamSimulationPlayer'
import { FilePreviewModal } from '../components/FilePreviewModal'
import { FlashcardPlayer } from '../components/FlashcardPlayer'
import { GlossaryPanel } from '../components/GlossaryPanel'
import { GuidePanel } from '../components/GuidePanel'
import { MaterialUploadForm } from '../components/MaterialUploadForm'
import { NextActionCard } from '../components/NextActionCard'
import { QuizFeed } from '../components/QuizFeed'
import { RetentionCurve } from '../components/RetentionCurve'
import { RetentionProgressBadge } from '../components/RetentionProgressBadge'
import { StudyTimer } from '../components/StudyTimer'
import { WeakTopicHeatmap } from '../components/WeakTopicHeatmap'
import { CourseNotesPanel } from '../components/CourseNotesPanel'
import { WorkspaceChrome } from '../components/WorkspaceChrome'
import { SavedQuestionsPage } from './SavedQuestionsPage'
import { ChapterCard } from '../components/CourseCard'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { confirmDialog } from '../stores/confirmStore'
import { getCardSummary, type ChapterCardSummary } from '../api/cardSummary'
import { ArrowRight, X } from 'lucide-react'

type LoadState = 'loading' | 'ready' | 'error'

type CourseTab = 'overview' | 'ask' | 'cards' | 'guide' | 'essay' | 'errors' | 'heatmap' | 'exam' | 'feed' | 'study' | 'smart' | 'draft'
// 13 sekme tek sıra hâlinde bilişsel yük eşiğinin (≤4 görünür seçenek) çok üstündeydi
// ve mobilde ilk ekranın tamamını kaplıyordu (2026-09-08 kritik incelemede tespit
// edildi). Öğrenci çalışma akışına göre 4 üst gruba ayrıldı; her grup ≤4 alt sekme
// taşır.
const COURSE_TAB_GROUPS = [
  { id: 'learn', label: 'Öğren', tabIds: ['overview', 'guide', 'study'] },
  { id: 'practice', label: 'Pratik Yap', tabIds: ['cards', 'feed', 'ask'] },
  { id: 'exam-prep', label: 'Sınava Hazırlan', tabIds: ['exam', 'heatmap', 'errors', 'smart'] },
  { id: 'homework', label: 'Ödev', tabIds: ['essay', 'draft'] },
] as const satisfies readonly { id: string; label: string; tabIds: readonly CourseTab[] }[]

/** İndeksleme ilerleme çubuğu — hedefe 1'er birim animasyonla yaklaşır. */
function JobProgressBar({ target }: { target: number }) {
  const progress = useAnimatedProgress(target)
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-24 overflow-hidden rounded-pill bg-stuhub-border">
        <span
          className="block h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
          style={{ width: `${Math.round(progress)}%` }}
        />
      </span>
      <span className="text-stuhub-text-secondary">%{Math.round(progress)}</span>
    </span>
  )
}

/** Chapter düzenleme mini formu — başlık (hafif, mevcut Form'dan bağımsız). */
function ChapterEditForm({
  chapter,
  onSubmit,
  onCancel,
}: {
  chapter: Chapter
  onSubmit: (title: string) => Promise<void>
  onCancel: () => void
}) {
  const [title, setTitle] = useState(chapter.title)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) {
      setError('Chapter başlığı boş olamaz.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit(trimmed)
    } catch {
      setError('Chapter güncellenemedi. Lütfen tekrar deneyin.')
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
        <label htmlFor={`chapter-edit-title-${chapter.id}`} className="mb-1 block text-sm font-medium">
          Chapter başlığı
        </label>
        <input
          id={`chapter-edit-title-${chapter.id}`}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
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

/** Ders defteri (notebook) landing sayfası — chapter + materyaller + genel quiz (Faz 1.3/2.2/5). */
export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const numericId = Number(courseId)

  const [course, setCourse] = useState<Course | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [jobs, setJobs] = useState<IndexingJob[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showChapterForm, setShowChapterForm] = useState(false)
  const [editingChapter, setEditingChapter] = useState<Chapter | null>(null)
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null)
  const [tab, setTab] = useState<CourseTab>('overview')
  // Chapter kart hover rotation verisi (§37) — tek istekte toplu (card-summary).
  const [cardSummaries, setCardSummaries] = useState<Map<number, ChapterCardSummary>>(new Map())

  useEffect(() => {
    const view = searchParams.get('view')
    const map: Record<string, CourseTab> = {
      'swipe-quiz': 'feed',
      'material-ask': 'ask',
      'flashcards': 'cards',
      'assignment-evaluation': 'essay',
      'assignment-draft-coach': 'draft',
      // Sıkıntı: dashboard kartları bu URL'leri açıyordu ama eşleme yoktu —
      // kullanıcı boş overview görüyordu (Hatalarım / Isı haritası "çalışmıyor").
      'errors': 'errors',
      'heatmap': 'heatmap',
    }
    if (view && map[view]) setTab(map[view])
    else if (!view) setTab('overview')
  }, [searchParams])

  // Klavye kısayolu 1-4: ders bölümleri arasında geçiş (Öğren/Pratik Yap/Sınava
  // Hazırlan/Ödev) — metin girişi odaktayken tetiklenmez (2026-09-08 kritik
  // incelemede "Alex/power-user" bulgusu: klavye kısayolu yoktu).
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      const typing =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.isContentEditable
      if (typing || event.metaKey || event.ctrlKey || event.altKey) return
      const index = Number(event.key) - 1
      const group = COURSE_TAB_GROUPS[index]
      if (group) setTab(group.tabIds[0])
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // genel quiz durumu — küresel üretim deposu (madde 2)
  // bugünün due kartları + oynatıcı (Faz V2.2)
  const [dueCards, setDueCards] = useState<DueCard[]>([])
  const [playingDue, setPlayingDue] = useState<DueCard[] | null>(null)
  // §42: ders görünümünde flashcard setleri chapter'a göre gruplu
  const [courseCardSets, setCourseCardSets] = useState<FlashcardSet[]>([])
  const [playingSet, setPlayingSet] = useState<FlashcardSet | null>(null)
  // sınav simülasyonu — seçilen sınav + oynatıcı sonucu (Plan #35/#44)
  const [simulatingExam, setSimulatingExam] = useState<{ id: number; title: string } | null>(null)
  const [examOutcome, setExamOutcome] = useState<{
    outcome: OverallOutcome
    missed: MissedQuestion[]
  } | null>(null)

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
      const [courseData, chapterList, materialList, jobList, dueCardList] =
        await Promise.all([
          coursesApi.get(numericId),
          chaptersApi.listByCourse(numericId),
          materialsApi.listByCourse(numericId),
          indexingApi.listByCourse(numericId),
          fetchDueCards(numericId, 20),
        ])
      setCourse(courseData)
      setChapters(chapterList)
      setMaterials(materialList)
      setJobs(jobList)
      setDueCards(dueCardList)
      setState('ready')
      // §42 kart gruplaması kritik değil — hata olsa grid render'ına devam etsin.
      listCourseFlashcardSets(numericId)
        .then(setCourseCardSets)
        .catch(() => undefined)
      // Kart özetleri kritik değil — hata bondanda grid rendersin devam etsin.
      getCardSummary(numericId)
        .then((summary) => {
          setCardSummaries(new Map(summary.chapters.map((chapter) => [chapter.chapter_id, chapter])))
        })
        .catch(() => undefined)
    } catch {
      setState('error')
      setError('Ders yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [numericId])

  const refreshDueCards = async () => {
    if (!numericId) return
    setDueCards(await fetchDueCards(numericId, 20))
    listCourseFlashcardSets(numericId)
      .then(setCourseCardSets)
      .catch(() => undefined)
  }

  const closeDuePlayer = () => {
    setPlayingDue(null)
    void refreshDueCards()
  }

  useEffect(() => {
    void load()
  }, [load])

  // İşlenen iş varsa 2 saniyede bir durumu tazele. Zincirleme setTimeout kullanılır:
  // setInterval, backend yavaşladığında biten isteği beklemeden yenisini kuyruğa
  // ekliyordu ve tarayıcının bağlantı bütçesi dolunca sayfa komple donuyordu.
  const hasActiveJobs = jobs.some((j) => j.status === 'pending' || j.status === 'processing')
  useEffect(() => {
    if (!hasActiveJobs) return
    let cancelled = false
    let timer = 0
    const tick = async () => {
      await refreshJobs()
      if (!cancelled) timer = window.setTimeout(tick, 2000)
    }
    timer = window.setTimeout(tick, 2000)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [hasActiveJobs, refreshJobs])

  const handleCreateChapter = async (title: string, slideFile: File) => {
    const created = await chaptersApi.create(numericId, title)
    try {
      await slidesApi.upload(created.id, slideFile)
    } catch {
      await chaptersApi.remove(created.id)
      throw new Error('Sunum yüklenemedi, chapter geri alındı. Lütfen tekrar deneyin.')
    }
    setShowChapterForm(false)
    await load()
  }

  const handleUpdateChapter = async (id: number, title: string) => {
    await chaptersApi.update(id, title)
    setEditingChapter(null)
    await load()
  }

  const handleDeleteChapter = async (id: number) => {
    if (!(await confirmDialog('Bu chapter silinecek. Emin misin?'))) return
    try {
      await chaptersApi.remove(id)
      setChapters((prev) => prev.filter((c) => c.id !== id))
    } catch {
      setError('Chapter silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const handleUploadMaterial = async (type: 'textbook' | 'slides' | 'syllabus', file: File) => {
    await materialsApi.upload(numericId, type, file)
    await load()
  }

  const handleDeleteMaterial = async (id: number) => {
    if (!(await confirmDialog('Bu materyal silinecek. Emin misin?'))) return
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

  // K5: düz `<a href>` indirmesi SaaS modda `Authorization` başlığını taşımıyor
  // ve 401 alıyordu — içerik artık authFetch + blob ile indirilir.
  const handleExportFlashcards = async (format: FlashcardExportFormat) => {
    const ok = await downloadAuthed(
      `/courses/${numericId}/flashcards/export?format=${format}`,
      `stuhub-kartlar-${numericId}.${format}`,
    )
    if (!ok) setError('Kartlar indirilemedi. Lütfen tekrar deneyin.')
  }

  const jobFor = (materialId: number): IndexingJob | undefined =>
    [...jobs].reverse().find((j) => j.material_id === materialId)

  // Aktif workspace'in listeye dönüş hedefi — yönerge §27: X current feature
  // listesine gider, global home'a DEĞİL. Genel dashboard'da chrome gizlenir.
  const viewParam = searchParams.get('view')
  const exitTo = viewParam ? `/dersler/${numericId}` : `/dersler/${numericId}`
  const isWorkspace = Boolean(viewParam) || tab !== 'overview'

  return (
    <section className="page-shell">
      {isWorkspace && <WorkspaceChrome exitTo={exitTo} exitLabel="Ders dashboard'una dön" />}
      <div className="page-header">
        <div>
          <h1 className="page-title">{course?.name ?? 'Ders'}</h1>
          {course?.instructor && <p className="page-subtitle">{course.instructor}</p>}
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

      {(searchParams.get('view') === 'notes') && <CourseNotesPanel courseId={numericId} />}

      {(searchParams.get('view') === 'saved') && <SavedQuestionsPage courseId={numericId} embedded />}

      {tab === 'overview' && !searchParams.get('view') && (
        <>
          <div className="secondary-grid mt-8">
            <button type="button" onClick={() => navigate(`/dersler/${numericId}?view=errors`)} className="glass-panel glass-interactive p-5 text-left" data-tour-id="course-mistakes">
              <p className="eyebrow">HATALARIM</p>
              <p className="mt-2 text-lg font-semibold">Son yaptığın hatalara göz at</p>
              <p className="mt-1 text-sm text-stuhub-text-secondary">Geçmiş quiz hatalarını incele ve tekrar çalış.</p>
            </button>
            <button type="button" onClick={() => navigate(`/dersler/${numericId}?view=heatmap`)} className="glass-panel glass-interactive p-5 text-left" data-tour-id="course-weak-topics">
              <p className="eyebrow">ZAYIF KONULAR</p>
              <p className="mt-2 text-lg font-semibold">En çok desteğe ihtiyaç duyan konular</p>
              <p className="mt-1 text-sm text-stuhub-text-secondary">Quiz, kart ve chat sinyallerini birlikte değerlendir.</p>
            </button>
          </div>

          {/* Chapter'lar */}
          <div className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="section-title">Chapter'lar</h2>
          {!showChapterForm && (
            <button
              type="button"
              onClick={() => setShowChapterForm(true)}
              className="btn-primary"
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

        <div className="mt-4 chapter-grid">
          {chapters.length === 0 && !showChapterForm && (
            <AddContentCard
              label="Chapter ekle"
              description="Henüz chapter yok — ilk chapter'ını ekleyerek başla."
              onClick={() => setShowChapterForm(true)}
            />
          )}
          {chapters.map((chapter) => (
            <div key={chapter.id} className="max-w-[420px] space-y-2">
              <ChapterCard
                chapter={chapter}
                summary={cardSummaries.get(chapter.id) ?? null}
                onEdit={(target) => setEditingChapter(target)}
                onDelete={(target) => void handleDeleteChapter(target.id)}
              />
              {editingChapter?.id === chapter.id && (
                <ChapterEditForm
                  chapter={chapter}
                  onSubmit={(title) => handleUpdateChapter(chapter.id, title)}
                  onCancel={() => setEditingChapter(null)}
                />
              )}
            </div>
          ))}
          {chapters.length > 0 && !showChapterForm && (
            <AddContentCard
              label="Chapter ekle"
              description="Yeni bir chapter ekleyerek konularını oluştur."
              onClick={() => setShowChapterForm(true)}
            />
          )}
        </div>
      </div>

      {/* Materyaller */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold">Materyaller</h2>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Ders kitapları (PDF) ve hoca sunumları burada toplanır; AI not ve quiz üretiminde kullanılır.
        </p>
        <div className="glass-panel mt-4 p-5">
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
                  className="flex items-center justify-between gap-4 rounded-control bg-stuhub-glass-2 px-4 py-2 text-sm"
                >
                  <span className="min-w-0">
                    <span className="font-medium">{material.display_name}</span>
                    <span className="ml-2 text-stuhub-text-secondary">
                      {material.type === 'textbook'
                        ? 'Kitap'
                        : material.type === 'slides'
                          ? 'Sunum'
                          : 'Müfredat'}
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
                    {/* Sunumlar (guide slides) hiç indekslenmez — job kaydı asla oluşmaz.
                        Bu materyaller için "Kuyruğa alınıyor" göstermek kalıcı/yanlış bir
                        "hâlâ işleniyor" izlenimi veriyordu (2026-09-08 kritik incelemede
                        tespit edildi: gerçekte materyal zaten kullanıma hazırdı). */}
                    {!job && material.type === 'textbook' && (
                      <span className="text-stuhub-text-secondary">Kuyruğa alınıyor…</span>
                    )}
                    {!job && material.type !== 'textbook' && (
                      <span className="text-stuhub-success">Kullanıma hazır</span>
                    )}
                    {job?.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => void handleIndex(material.id)}
                        className="rounded-control px-3 py-1 text-xs font-medium text-stuhub-error transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10"
                      >
                        Tekrar dene
                      </button>
                    )}
                    {material.file_ext === 'pdf' && (
                      <button
                        type="button"
                        onClick={() => setPreviewMaterial(material)}
                        className="rounded-control px-3 py-1 text-xs font-medium text-stuhub-accent transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
                      >
                        Önizle
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void handleDeleteMaterial(material.id)}
                      className="rounded-control p-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10 hover:text-stuhub-error"
                      title="Sil"
                      aria-label="Materyali sil"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
        </>
      )}

      {previewMaterial && (
        <FilePreviewModal
          path={`/materials/${previewMaterial.id}/file`}
          title={previewMaterial.display_name}
          onClose={() => setPreviewMaterial(null)}
        />
      )}

      {tab === 'cards' && (
        <>
          {/* Bugünün kartları — due tekrar kuyruğu (Faz V2.2) */}
          <div className="mt-12">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-xl font-semibold">Bugünün Kartları</h2>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => void handleExportFlashcards('apkg')}
              className="glass-panel-subtle glass-interactive rounded-control px-3 py-1 text-xs font-medium text-stuhub-text-secondary"
            >
              Tüm kartları Anki'ye aktar (.apkg)
            </button>
            <button
              type="button"
              onClick={() => void handleExportFlashcards('csv')}
              className="glass-panel-subtle glass-interactive rounded-control px-3 py-1 text-xs font-medium text-stuhub-text-secondary"
            >
              CSV
            </button>
          </div>
        </div>
        {playingDue ? (
          <div className="mt-4">
            <FlashcardPlayer
              dueCards={playingDue}
              onFinished={closeDuePlayer}
              onExit={closeDuePlayer}
            />
          </div>
        ) : dueCards.length > 0 ? (
          <div className="glass-panel mt-4 flex items-center justify-between px-5 py-4">
            <p className="text-sm text-stuhub-text-secondary">
              {dueCards.length} kart tekrar bekliyor
            </p>
            <button
              type="button"
              onClick={() => setPlayingDue(dueCards)}
              className="btn-primary"
            >
              Çalış
            </button>
          </div>
        ) : (
          <p className="mt-1 text-sm text-stuhub-text-secondary">Tekrar bekleyen kart yok.</p>
        )}
      </div>

          {/* §42: tüm setler — chapter'a göre gruplu, dikey */}
          <div className="mt-12">
            {playingSet ? (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Kart Çalışımı</h2>
                  <button
                    type="button"
                    className="glass-panel-subtle glass-interactive rounded-control px-3 py-1 text-xs font-medium text-stuhub-text-secondary"
                    onClick={() => setPlayingSet(null)}
                  >
                    Sete dön
                  </button>
                </div>
                <div className="mt-4">
                  <FlashcardPlayer
                    dueCards={playingSet.cards_json.map((card, cardIndex) => ({
                      set_id: playingSet.id,
                      card_index: cardIndex,
                      card,
                      review: null,
                      due: true,
                    }))}
                    onFinished={() => {
                      setPlayingSet(null)
                      void refreshDueCards()
                    }}
                    onExit={() => setPlayingSet(null)}
                  />
                </div>
              </>
            ) : (
              <>
            <h2 className="text-xl font-semibold">Chapter'lara Göre Kartlar</h2>
            {courseCardSets.length === 0 && (
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Henüz kart seti yok. Bir chapter açıp “Kart Oluştur” ile başla.
              </p>
            )}
            {chapters.map((chapter) => {
              const chapterSets = courseCardSets.filter((set) => set.chapter_id === chapter.id)
              if (chapterSets.length === 0) return null
              return (
                <div key={chapter.id} className="mt-6">
                  <p className="eyebrow">{chapter.title}</p>
                  <div className="list-stack mt-3">
                    {chapterSets.map((set) => (
                      <button
                        key={set.id}
                        type="button"
                        className="glass-panel glass-interactive list-card text-left"
                        onClick={() => setPlayingSet(set)}
                      >
                        <div>
                          <p className="font-medium">
                            {new Date(set.created_at ?? Date.now()).toLocaleDateString('tr-TR')} tarihli set
                          </p>
                          <p className="mt-1 text-xs text-stuhub-text-secondary">{set.card_count} kart</p>
                        </div>
                        <ArrowRight size={17} aria-hidden="true" />
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
              </>
            )}
          </div>
        </>
      )}

      {tab === 'ask' && (
        <>
          {/* Materyale Sor */}
          <div className="mt-12">
        <h2 className="text-xl font-semibold">Materyale Sor</h2>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          Ders materyaline soru sorun; yanıtlar kaynak atıflı gelir.
        </p>
        <div className="mt-4">
          <ChatPanel courseId={numericId} />
        </div>
      </div>
        </>
      )}

      {tab === 'guide' && <GuidePanel scope="course" scopeId={numericId} />}

      {tab === 'essay' && (
        <>
          {/* Ödev değerlendirme — AI puanlama (Faz V2.5) */}
          <div className="mt-12">
            <h2 className="text-xl font-semibold">Ödev Değerlendir</h2>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              Ödev metnini yapıştır; AI ölçütlere göre puanlayıp güçlü/zayıf yönleriyle geri
              bildirim verir.
            </p>
            <div className="mt-4">
              <EssayGraderForm courseId={numericId} />
            </div>
          </div>
        </>
      )}

      {tab === 'errors' && <span data-tour-id="course-mistakes" className="block"><ErrorLogPanel courseId={numericId} /></span>}

      {tab === 'heatmap' && <span data-tour-id="course-weak-topics" className="block"><WeakTopicHeatmap courseId={numericId} /></span>}

      {tab === 'exam' && (
        <div className="mt-8 space-y-8">
          {examOutcome ? (
            <div className="glass-panel space-y-4 p-5">
              <h2 className="text-xl font-semibold">Sınav Sonucu</h2>
              <p className="text-sm text-stuhub-text-secondary">
                Puan: {examOutcome.outcome.score} — {examOutcome.missed.length} soru kaçırıldı.
              </p>
              {examOutcome.missed.length > 0 && (
                <ExamPostmortemForm
                  examId={simulatingExam?.id ?? 0}
                  missedQuestions={examOutcome.missed}
                  onSubmitted={() => setExamOutcome(null)}
                />
              )}
              <button
                type="button"
                onClick={() => {
                  setExamOutcome(null)
                  setSimulatingExam(null)
                }}
                className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
              >
                Kapat
              </button>
            </div>
          ) : simulatingExam ? (
            <ExamSimulationPlayer
              courseId={numericId}
              examId={simulatingExam.id}
              examTitle={simulatingExam.title}
              onFinished={(outcome) => {
                const missed: MissedQuestion[] = outcome.results
                  .filter((r) => (r.score != null ? r.score < 10 : r.correct === false))
                  .map((r) => ({ qid: r.qid, question: r.question }))
                setExamOutcome({ outcome, missed })
              }}
            />
          ) : (
            <>
              <ExamCountdownPanel
                courseId={numericId}
                chapters={chapters}
                onSimulate={(exam) => setSimulatingExam({ id: exam.id, title: exam.title })}
              />
              <RetentionCurve courseId={numericId} />
            </>
          )}
        </div>
      )}

      {tab === 'feed' && (
        <div className="mt-8">
          <QuizFeed courseId={numericId} />
        </div>
      )}

      {tab === 'study' && (
        <div className="mt-8 space-y-8">
          <ComparisonTable courseId={numericId} />
          <GlossaryPanel courseId={numericId} />
        </div>
      )}

      {tab === 'smart' && (
        <div className="mt-8 space-y-8">
          <div className="glass-panel p-5">
            <NextActionCard
              courseId={numericId}
              onOpenChapter={(chapterId) => navigate(`/dersler/${numericId}/defter/${chapterId}`)}
            />
          </div>
          <RetentionProgressBadge courseId={numericId} />
          <StudyTimer courseId={numericId} />
          <AbandonedTopicsList courseId={numericId} />
        </div>
      )}

      {tab === 'draft' && (
        <div className="mt-8">
          <EssayDraftCoach courseId={numericId} />
        </div>
      )}
    </section>
  )
}
