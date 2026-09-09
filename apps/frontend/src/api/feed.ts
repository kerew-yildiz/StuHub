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
  /** Kullanıcı bu soruyu "kaydedilenler" listesine eklemiş mi. */
  saved: boolean
}

/** Tek parti feed yanıtı (GET /courses/{id}/feed). */
export interface FeedBatch {
  items: FeedQuestion[]
  /** Sunucu havuzunda servise hazır bekleyen soru sayısı. */
  pool_ready: number
  /** Arka planda LLM ile yeni soru üretimi sürüyor mu? */
  generating: boolean
}

/** Konu bazlı ustalık ilerlemesi — chapter/ders seviyesinde ortak şekil. */
export interface MasteryTopic {
  topic: string
  correct: number
  target: number
}

/** GET /courses/{id}/mastery, GET /chapters/{id}/mastery ortak yanıt şekli.
 * `percent` = sum(min(dogru_t,5)) / (konu_sayisi*5) * 100. */
export interface Mastery {
  percent: number
  correct: number
  total: number
  topics: MasteryTopic[]
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

/** Havuzdan bir parti soru çeker; istek anında LLM çağrılmaz (GET /courses/{id}/feed).
 * `chapterId` verilirse akış o chapter'a daraltılır. */
export async function fetchFeed(
  courseId: number,
  limit = 10,
  chapterId?: number,
): Promise<FeedBatch> {
  const query = chapterId !== undefined ? `limit=${limit}&chapter_id=${chapterId}` : `limit=${limit}`
  const response = await authFetch(`/courses/${courseId}/feed?${query}`)
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

/** Ders seviyesinde ustalık ilerlemesi (GET /courses/{id}/mastery). */
export async function fetchCourseMastery(courseId: number): Promise<Mastery> {
  const response = await authFetch(`/courses/${courseId}/mastery`)
  if (!response.ok) {
    throw new Error('Ustalık verisi alınamadı.')
  }
  return (await response.json()) as Mastery
}

/** Chapter seviyesinde ustalık ilerlemesi (GET /chapters/{id}/mastery). */
export async function fetchChapterMastery(chapterId: number): Promise<Mastery> {
  const response = await authFetch(`/chapters/${chapterId}/mastery`)
  if (!response.ok) {
    throw new Error('Ustalık verisi alınamadı.')
  }
  return (await response.json()) as Mastery
}

/** Soruyu kaydedilenler listesine ekler (POST /feed/{feed_id}/save). */
export async function saveQuestion(feedId: number): Promise<void> {
  const response = await authFetch(`/feed/${feedId}/save`, { method: 'POST' })
  if (!response.ok) {
    throw new Error('Soru kaydedilemedi. Lütfen tekrar deneyin.')
  }
}

/** Sorunun kaydını kaldırır (DELETE /feed/{feed_id}/save). */
export async function unsaveQuestion(feedId: number): Promise<void> {
  const response = await authFetch(`/feed/${feedId}/save`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error('Kayıt kaldırılamadı. Lütfen tekrar deneyin.')
  }
}
