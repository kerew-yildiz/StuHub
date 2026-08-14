import { BASE_URL } from './client'
import type { Citation } from './notes'

/** Flashcard (backend kart şeması ile birebir — YETENEKLER/09). */
export interface Flashcard {
  topic: string
  front: string
  back: string
  type: 'qa' | 'term'
  citations: Citation[]
}

/** Kayıtlı flashcard seti (backend FlashcardSetOut ile birebir). */
export interface FlashcardSet {
  id: number
  chapter_id: number
  cards_json: Flashcard[]
  card_count: number
  created_at?: string
  model_used?: string | null
  warnings?: string[]
}

/** SM-2 tekrar durumu (Again/Hard/Good/Easy — YETENEKLER/09). */
export interface ReviewState {
  ease_factor: number
  interval_days: number
  repetitions: number
  due_at: string | null
  last_rating: string | null
}

/** Review sonrası dönüş — ReviewState + set/kart adresi. */
export interface ReviewResult extends ReviewState {
  set_id: number
  card_index: number
}

/** Due kuyruğundaki tek kart. */
export interface DueCard {
  set_id: number
  card_index: number
  card: Flashcard
  review: ReviewState | null
  due: boolean
}

/** SM-2 değerlendirme dörtlüsü. */
export type Rating = 'again' | 'hard' | 'good' | 'easy'

export interface FlashcardStreamHandlers {
  onStatus?: (percent: number, message: string) => void
  onDone?: (set: FlashcardSet) => void
  onError?: (message: string) => void
}

/** Flashcard üretimini POST edip SSE akışını okur (Faz V2.2). */
export async function streamFlashcardGeneration(
  chapterId: number,
  handlers: FlashcardStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/chapters/${chapterId}/flashcards`, { method: 'POST' })
  } catch {
    handlers.onError?.('Kart üretimi başlatılamadı. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Kart üretimi başlatılamadı. Lütfen tekrar deneyin.')
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
          id?: number
          chapter_id?: number
          cards_json?: Flashcard[]
          card_count?: number
          warnings?: string[]
        }
        try {
          event = JSON.parse(dataLine.slice(6))
        } catch {
          continue
        }
        if (event.type === 'status') {
          handlers.onStatus?.(event.percent ?? 0, event.message ?? '')
        } else if (event.type === 'done') {
          handlers.onDone?.({
            id: event.id ?? 0,
            chapter_id: event.chapter_id ?? 0,
            cards_json: event.cards_json ?? [],
            card_count: event.card_count ?? 0,
            warnings: event.warnings ?? [],
          })
        } else if (event.type === 'error') {
          handlers.onError?.(event.message ?? 'Kart üretimi başarısız oldu.')
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Chapter'ın TÜM flashcard setleri (yeniden eskiye). */
export async function listFlashcardSets(chapterId: number): Promise<FlashcardSet[]> {
  const response = await fetch(`${BASE_URL}/chapters/${chapterId}/flashcard-sets`)
  if (!response.ok) return []
  return (await response.json()) as FlashcardSet[]
}

/** Tek flashcard seti (404 ise null). */
export async function getFlashcardSet(setId: number): Promise<FlashcardSet | null> {
  const response = await fetch(`${BASE_URL}/flashcard-sets/${setId}`)
  if (!response.ok) return null
  return (await response.json()) as FlashcardSet
}

/** Flashcard setini kalıcı olarak siler (204). */
export async function deleteFlashcardSet(setId: number): Promise<void> {
  await fetch(`${BASE_URL}/flashcard-sets/${setId}`, { method: 'DELETE' })
}

/** Dersin bugünkü due kartları (kurs bazlı; vadesi geçen önce). */
export async function fetchDueCards(courseId: number, limit = 20): Promise<DueCard[]> {
  try {
    const response = await fetch(
      `${BASE_URL}/courses/${courseId}/flashcards/due?limit=${limit}`,
    )
    if (!response.ok) return []
    return (await response.json()) as DueCard[]
  } catch {
    return []
  }
}

/** SM-2 review gönderir; güncellenmiş kart durumunu döner. */
export async function submitReview(
  setId: number,
  cardIndex: number,
  rating: Rating,
): Promise<ReviewResult> {
  const response = await fetch(`${BASE_URL}/flashcard-sets/${setId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_index: cardIndex, rating }),
  })
  if (!response.ok) {
    throw new Error('Tekrar kaydedilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as ReviewResult
}
