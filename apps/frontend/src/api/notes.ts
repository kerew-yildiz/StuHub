import { authFetch } from './client'

/** Kayıtlı not (backend NoteOut ile birebir). */
export interface Citation {
  id: number
  source_type: 'textbook' | 'slides' | 'note' | 'web'
  source_id: number | null
  page: number | null
  slide: number | null
  chunk_id: string | null
  quote: string
  /** Web kaynaklı atıflar için kaynak başlığı (source_type: "web"). */
  title?: string | null
  /** Web kaynaklı atıflar için kaynak URL'si (source_type: "web"). */
  url?: string | null
}

export interface NoteTopic {
  topic: string
  citations: Citation[]
}

export interface SavedNote {
  id: number
  chapter_id: number
  content_md: string
  citations_json: { topics: NoteTopic[] }
  topics_json: Array<{ topic: string; keywords: string[]; slide_refs: number[] }>
  generated_at: string
  model_used: string | null
}

export interface NoteStreamHandlers {
  onStatus?: (percent: number, message: string) => void
  onDelta?: (text: string) => void
  onDone?: (note: SavedNote) => void
  onError?: (message: string) => void
}

/** Not üretimini POST edip SSE akışını okur (Faz 3.2). */
export async function streamNoteGeneration(
  chapterId: number,
  handlers: NoteStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await authFetch(`/chapters/${chapterId}/notes`, { method: 'POST' })
  } catch {
    handlers.onError?.('Not üretimi başlatılamadı. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Not üretimi başlatılamadı. Lütfen tekrar deneyin.')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const chunk = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '))
        if (!dataLine) continue
        let event: {
          type: string
          percent?: number
          message?: string
          text?: string
          note?: SavedNote
        }
        try {
          event = JSON.parse(dataLine.slice(6))
        } catch {
          continue
        }
        if (event.type === 'status') {
          handlers.onStatus?.(event.percent ?? 0, event.message ?? '')
        } else if (event.type === 'delta' && event.text) {
          handlers.onDelta?.(event.text)
        } else if (event.type === 'done' && event.note) {
          handlers.onDone?.(event.note)
        } else if (event.type === 'error') {
          handlers.onError?.(event.message ?? 'Üretim başarısız oldu.')
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Chapter'ın en güncel kayıtlı notu. */
/** Not içeriğini düzenler (yönerge §39). */
export async function updateNote(noteId: number, contentMd: string): Promise<SavedNote> {
  const response = await authFetch(`/notes/${noteId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content_md: contentMd }),
  })
  if (!response.ok) throw new Error('Not güncellenemedi')
  return (await response.json()) as SavedNote
}

/** Chapter'ın tüm kayıtlı notları — yeniden eskiye (not arşivi). */
export async function listChapterNotes(chapterId: number): Promise<SavedNote[]> {
  const response = await authFetch(`/chapters/${chapterId}/notes/archive`)
  if (!response.ok) return []
  return (await response.json()) as SavedNote[]
}

/** Notu siler (yönerge §39 — çağıran taraf confirmation modal'ı zorunlu kılar). */
export async function deleteNote(noteId: number): Promise<void> {
  const response = await authFetch(`/notes/${noteId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error('Not silinemedi')
}

export async function getNote(chapterId: number): Promise<SavedNote | null> {
  const response = await authFetch(`/chapters/${chapterId}/notes`)
  if (!response.ok) return null
  return (await response.json()) as SavedNote
}

/** Notu PDF olarak indirir (Türkçe karakter destekli).
 * variant: "physical" (baskı dostu, siyah logo, marka header) | "digital" (koyu StuHub teması). */
export type PdfVariant = 'physical' | 'digital'

export async function exportNotePdf(
  noteId: number,
  variant: PdfVariant = 'physical',
  /** İndirme dosya adı (uzantısız) — chapter başlığından türetilir.
   * Varsayılan eski kalıp (geriye uyumluluk; çağıranlar artık başlık veriyor). */
  filename = `stuhub-not-${noteId}-${variant}`,
): Promise<void> {
  const response = await authFetch(`/notes/${noteId}/export?variant=${variant}`)
  if (!response.ok) {
    throw new Error('PDF oluşturulamadı. Lütfen tekrar deneyin.')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${sanitizeFilename(filename)}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Dosya adını platformda geçersiz karakterlerden temizler (Windows yasaklıları dahil). */
function sanitizeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|\x00-\x1f]/g, '').trim() || 'not'
}

/** Atıf pop-up'ı için kaynak parça (Yetenek 06 §4). */
export interface ResolvedChunk {
  chunk_id: string
  course_id: number
  material_id: number
  text: string
  page: number | null
  slide: number | null
}

export async function resolveCitation(chunkId: string): Promise<ResolvedChunk | null> {
  try {
    const response = await authFetch(`/citations/${encodeURIComponent(chunkId)}`)
    if (!response.ok) return null
    return (await response.json()) as ResolvedChunk
  } catch {
    return null
  }
}
