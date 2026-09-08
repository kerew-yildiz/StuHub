import { authFetch } from './client'

/** Hata günlüğü kaydı — geçmiş denemelerdeki tek bir yanlış cevap (backend ile birebir). */
export interface ErrorLogEntry {
  question_text: string
  given_answer: string
  correct_answer: string
  topic: string
  quiz_id: number
  /** Chapter quizi ise bölüm kimliği; genel quiz hatalarında null. */
  chapter_id: number | null
  created_at: string
  /** Aynı konuda (seçilen zaman aralığında) toplam kaç kez yanlış yapıldığı. */
  repeat_count: number
}

/** Hata listesi süzgeçleri (hepsi opsiyonel). */
export interface ErrorLogParams {
  /** Yalnızca bu konudaki hatalar */
  topic?: string
  /** ISO tarih (YYYY-MM-DD veya tam ISO); bu andan sonraki hatalar */
  since?: string
  /** Yalnızca 2+ kez yanlış yapılan konular */
  onlyRepeated?: boolean
}

/** Dersteki tüm yanlış cevapları yeniden eskiye döner (GET /courses/{id}/errors). */
export async function listErrors(
  courseId: number,
  params: ErrorLogParams = {},
): Promise<ErrorLogEntry[]> {
  const query = new URLSearchParams()
  if (params.topic) query.set('topic', params.topic)
  if (params.since) query.set('since', params.since)
  if (params.onlyRepeated) query.set('only_repeated', 'true')
  const search = query.toString()
  const suffix = search ? `?${search}` : ''

  const response = await authFetch(`/courses/${courseId}/errors${suffix}`)
  if (!response.ok) {
    throw new Error('Hata günlüğü alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as ErrorLogEntry[]
}

/** Kurtarma quizindeki tek soru (backend `ErrorQuizQuestion` ile birebir). */
export interface ErrorQuizQuestion {
  topic: string
  question: string
  options: string[]
  correct_index: number
  explanation: string
  feedback_correct: string
  feedback_wrong: string
  citations: Record<string, unknown>[]
  difficulty: string | null
}

/** Kurtarma quizi üretim sonucu (backend `ErrorQuizOut` ile birebir). */
export interface ErrorQuizResult {
  course_id: number
  /** Kullanılan konular — `topics` verilmediyse hata günlüğünden otomatik seçilenler. */
  topics: string[]
  questions: ErrorQuizQuestion[]
}

/** Hata günlüğündeki konulardan YENİ sorular üretir (Plan #6, POST /courses/{id}/errors/quiz).
 *
 * `topics` verilmezse hata günlüğündeki en sık yanlış yapılan konular otomatik seçilir.
 * Üretilen sorular hata günlüğündeki AYNI soruları asla tekrar etmez. */
export async function generateErrorQuiz(
  courseId: number,
  topics?: string[],
): Promise<ErrorQuizResult> {
  const response = await authFetch(`/courses/${courseId}/errors/quiz`, {
    method: 'POST',
    body: JSON.stringify({ topics: topics ?? null }),
  })
  if (!response.ok) {
    throw new Error('Kurtarma quizi üretilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as ErrorQuizResult
}
