import { authFetch } from './client'

/** GET /saved-questions öğesi — ders/chapter bilgisiyle zenginleştirilmiş kaydedilmiş soru. */
export interface SavedQuestion {
  feed_id: number
  question: string
  options: string[]
  correct_index: number
  explanation: string
  topic: string | null
  chapter_id: number
  chapter_title: string
  course_id: number
  course_name: string
  saved_at: string
}

/** Kullanıcının kaydettiği tüm soruları listeler (GET /saved-questions). */
export async function listSavedQuestions(): Promise<SavedQuestion[]> {
  const response = await authFetch('/saved-questions')
  if (!response.ok) {
    throw new Error('Kaydedilen sorular alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as SavedQuestion[]
}
