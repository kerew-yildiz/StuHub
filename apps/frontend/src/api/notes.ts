import { BASE_URL } from './client'

/** Kayıtlı not (backend NoteOut ile birebir). */
export interface Citation {
  id: number
  source_type: 'textbook' | 'slides' | 'note'
  source_id: number | null
  page: number | null
  slide: number | null
  chunk_id: string | null
  quote: string
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
    response = await fetch(`${BASE_URL}/chapters/${chapterId}/notes`, { method: 'POST' })
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
export async function getNote(chapterId: number): Promise<SavedNote | null> {
  const response = await fetch(`${BASE_URL}/chapters/${chapterId}/notes`)
  if (!response.ok) return null
  return (await response.json()) as SavedNote
}

/** Notu PDF olarak indirir (Türkçe karakter destekli). */
export async function exportNotePdf(noteId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/notes/${noteId}/export`)
  if (!response.ok) {
    throw new Error('PDF oluşturulamadı. Lütfen tekrar deneyin.')
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `stuhub-not-${noteId}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
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
    const response = await fetch(`${BASE_URL}/citations/${encodeURIComponent(chunkId)}`)
    if (!response.ok) return null
    return (await response.json()) as ResolvedChunk
  } catch {
    return null
  }
}
