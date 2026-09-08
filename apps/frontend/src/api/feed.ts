import { authFetch } from './client'
import type { Citation } from './notes'

/** Zorluk kademesi — backend `feed_questions.difficulty` ile birebir. */
export type FeedDifficulty = 'easy' | 'medium' | 'hard'

/** Feed'de servis edilen tek soru.
 *
 * Doğru cevap ALANI YOKTUR: havuzdan servis eden uç `correct_index`/`answer_key`
 * sızdırmaz, doğru cevap yalnızca `POST /feed/{id}/answer` yanıtında döner. */
export interface FeedQuestion {
  feed_id: number
  question: string
  options: string[]
  topic: string | null
  chapter_id: number | null
  difficulty: FeedDifficulty | null
}

/** Tek parti feed yanıtı (GET /courses/{id}/feed). */
export interface FeedBatch {
  items: FeedQuestion[]
  /** Sunucu havuzunda servise hazır bekleyen soru sayısı. */
  pool_ready: number
  /** Arka planda LLM ile yeni soru üretimi sürüyor mu? */
  generating: boolean
}

/** Cevap değerlendirmesi (POST /feed/{feed_id}/answer). */
export interface AnswerResult {
  correct: boolean
  correct_index: number
  explanation: string
  /** Sözleşmede `unknown[]|null`; backend not/quiz atıflarıyla aynı şekli üretir. */
  citations: Citation[] | null
  note_id: number | null
  chapter_id: number | null
}

/** Havuzdan bir parti soru çeker; istek anında LLM çağrılmaz (GET /courses/{id}/feed). */
export async function fetchFeed(courseId: number, limit = 10): Promise<FeedBatch> {
  const response = await authFetch(`/courses/${courseId}/feed?limit=${limit}`)
  if (!response.ok) {
    throw new Error('Sorular alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as FeedBatch
}

/** Cevabı gönderir ve değerlendirmeyi döner (POST /feed/{feed_id}/answer). */
export async function answerFeed(
  feedId: number,
  selectedIndex: number,
  elapsedMs: number,
): Promise<AnswerResult> {
  const response = await authFetch(`/feed/${feedId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ selected_index: selectedIndex, elapsed_ms: elapsedMs }),
  })
  if (!response.ok) {
    throw new Error('Cevap gönderilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as AnswerResult
}

/** Soruyu cevaplamadan geçer (POST /courses/{id}/feed/skip). */
export async function skipFeed(courseId: number, feedId: number): Promise<void> {
  const response = await authFetch(`/courses/${courseId}/feed/skip`, {
    method: 'POST',
    body: JSON.stringify({ feed_id: feedId }),
  })
  if (!response.ok) {
    throw new Error('Soru atlanamadı. Lütfen tekrar deneyin.')
  }
}
