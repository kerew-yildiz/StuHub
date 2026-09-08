import { BookOpen, FilePdf, X } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

import { chaptersApi } from '../api/chapters'
import { getNote, type Citation } from '../api/notes'
import { CitationPopup } from './CitationPopup'
import { FilePreviewModal } from './FilePreviewModal'

export interface WrongAnswerLinksProps {
  /** Yanlış cevaplanan sorunun atıfları — boşsa hiçbir bağlantı gösterilmez (kırık link üretilmez). */
  citations: Citation[]
  /** Sorunun konu adı; not içindeki bölüm başlığı bununla eşleştirilir. */
  topic?: string | null
  /** Bölüm quizi: notun ait olduğu chapter (doğrudan tek not okunur). */
  chapterId?: number | null
  /** Genel quiz: soru hangi bölümden geldiği bilinmediği için dersin bölümleri taranır. */
  courseId?: number | null
}

const HEADING_RE = /^(#{1,4})\s+(.+?)\s*$/

interface NoteSection {
  chapterTitle: string | null
  heading: string
  body: string
}

/** Başlık ↔ konu adı esnek eşleşmesi (NoteViewer ile aynı kural: LLM başlıkları konu adından sapabilir). */
function topicMatches(heading: string, topic: string): boolean {
  const normalize = (s: string) => s.toLowerCase().replace(/[^\w\s]/g, '').trim()
  const a = normalize(heading)
  const b = normalize(topic)
  if (!a || !b) return false
  if (a === b) return true
  if (b.length >= 4 && a.includes(b)) return true
  return a.length >= 4 && b.includes(a)
}

/** `content_md` içinden konuya karşılık gelen başlık bloğunu çıkarır (backend `_section_for_topic` ile aynı mantık). */
function sectionForTopic(contentMd: string, topic: string): { heading: string; body: string } | null {
  let heading: string | null = null
  const body: string[] = []
  for (const line of contentMd.split('\n')) {
    const match = line.match(HEADING_RE)
    if (match) {
      if (heading) break // bir sonraki başlık bölümü bitirir
      if (topicMatches(match[2], topic)) heading = match[2]
      continue
    }
    if (heading) body.push(line)
  }
  return heading ? { heading, body: body.join('\n').trim() } : null
}

/** Konuya ait not bölümünü bulur; chapter verilmemişse dersin bölümleri sırayla taranır. */
async function findNoteSection(
  topic: string,
  chapterId: number | null,
  courseId: number | null,
): Promise<NoteSection | null> {
  let chapters: Array<{ id: number; title: string | null }> = []
  if (chapterId != null) {
    chapters = [{ id: chapterId, title: null }]
  } else if (courseId != null) {
    try {
      chapters = (await chaptersApi.listByCourse(courseId)).map((c) => ({ id: c.id, title: c.title }))
    } catch {
      return null
    }
  }

  for (const chapter of chapters) {
    const note = await getNote(chapter.id).catch(() => null)
    if (!note) continue
    const section = sectionForTopic(note.content_md, topic)
    if (section) return { chapterTitle: chapter.title, ...section }
  }
  return null
}

/** Not bölümü penceresi — yanlış cevabın karşılığı olan not parçasını gösterir. */
function NoteSectionModal({
  state,
  section,
  topic,
  onClose,
}: {
  state: 'loading' | 'ready' | 'missing'
  section: NoteSection | null
  topic: string
  onClose: () => void
}) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="note-section-title"
        className="max-h-[80vh] w-full max-w-2xl overflow-y-auto glass-panel p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="note-section-title" className="text-lg font-semibold">
              Notta: {section?.heading ?? topic}
            </h2>
            {section?.chapterTitle && (
              <p className="mt-1 text-sm text-stuhub-text-secondary">{section.chapterTitle}</p>
            )}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-control p-1.5 text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover hover:text-stuhub-text active:scale-[0.98]"
            aria-label="Kapat"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="mt-4 max-w-[68ch] text-sm leading-relaxed">
          {state === 'loading' && <p className="text-stuhub-text-secondary">Not yükleniyor…</p>}
          {state === 'missing' && (
            <p className="text-stuhub-text-secondary">
              Bu konuya ait not bölümü bulunamadı. Notu yeniden üretmen gerekebilir.
            </p>
          )}
          {state === 'ready' && section && (
            <ReactMarkdown
              components={{
                h1: ({ children }) => <h3 className="mt-3 mb-2 text-base font-semibold">{children}</h3>,
                h2: ({ children }) => <h3 className="mt-3 mb-2 text-base font-semibold">{children}</h3>,
                h3: ({ children }) => <h3 className="mt-3 mb-2 text-base font-semibold">{children}</h3>,
                ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-6">{children}</ul>,
                ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1 pl-6">{children}</ol>,
                p: ({ children }) => <p className="mt-2">{children}</p>,
              }}
            >
              {section.body}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  )
}

/** Yanlış cevap → nota ve kaynak PDF sayfasına derin bağlantılar (plan maddesi 4).
 *
 * Atıfsız soruda hiçbir şey render edilmez; PDF yolu atıfın `source_id`'sinden
 * (= `material_id`, bkz. `note_generator._chunk_to_citation`) türetilir. */
export function WrongAnswerLinks({ citations, topic, chapterId, courseId }: WrongAnswerLinksProps) {
  const [noteOpen, setNoteOpen] = useState(false)
  const [noteState, setNoteState] = useState<'loading' | 'ready' | 'missing'>('loading')
  const [section, setSection] = useState<NoteSection | null>(null)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [preview, setPreview] = useState<{ path: string; title: string; page?: number } | null>(null)

  if (citations.length === 0) return null

  // PDF'e gidebilecek atıf: materyal kimliği (source_id) olan kitap/sunum atıfı
  const pdfCitation = citations.find(
    (c) => c.source_id != null && (c.source_type === 'textbook' || c.source_type === 'slides'),
  )
  // PDF yoksa en az kaynak parçayı gösterebilecek atıf
  const textCitation = citations.find((c) => Boolean(c.chunk_id) || Boolean(c.quote))
  const sourceCitation = pdfCitation ?? textCitation
  const canOpenNote = Boolean(topic) && (chapterId != null || courseId != null)
  if (!sourceCitation && !canOpenNote) return null

  const locationLabel =
    sourceCitation?.page != null
      ? `sayfa ${sourceCitation.page}`
      : sourceCitation?.slide != null
        ? `slide ${sourceCitation.slide}`
        : null

  const handleOpenNote = async () => {
    if (!topic) return
    setNoteOpen(true)
    if (section) {
      setNoteState('ready')
      return
    }
    setNoteState('loading')
    const found = await findNoteSection(topic, chapterId ?? null, courseId ?? null)
    if (found) {
      setSection(found)
      setNoteState('ready')
    } else {
      setNoteState('missing')
    }
  }

  const handleOpenSource = () => {
    if (pdfCitation?.source_id != null) {
      setPreview({
        path: `/materials/${pdfCitation.source_id}/file`,
        title: locationLabel ? `Kaynak · ${locationLabel}` : 'Kaynak',
        page: pdfCitation.page ?? undefined,
      })
      return
    }
    if (textCitation) setActiveCitation(textCitation)
  }

  const chipClass =
    'glass-panel-subtle glass-interactive inline-flex items-center gap-1.5 rounded-chip px-3 py-1.5 text-xs font-medium text-stuhub-text-secondary'

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {canOpenNote && (
        <button type="button" onClick={() => void handleOpenNote()} className={chipClass}>
          <BookOpen size={14} aria-hidden="true" />
          Notta gör
        </button>
      )}
      {sourceCitation && (
        <button type="button" onClick={handleOpenSource} className={chipClass}>
          <FilePdf size={14} aria-hidden="true" />
          {locationLabel ? `Kaynak sayfa · ${locationLabel}` : 'Kaynak sayfa'}
        </button>
      )}

      {noteOpen && topic && (
        <NoteSectionModal
          state={noteState}
          section={section}
          topic={topic}
          onClose={() => setNoteOpen(false)}
        />
      )}
      {preview && (
        <FilePreviewModal
          path={preview.path}
          title={preview.title}
          page={preview.page}
          onClose={() => setPreview(null)}
        />
      )}
      {activeCitation && (
        <CitationPopup
          citation={activeCitation}
          preloadedText={activeCitation.quote || undefined}
          onClose={() => setActiveCitation(null)}
        />
      )}
    </div>
  )
}

export default WrongAnswerLinks
