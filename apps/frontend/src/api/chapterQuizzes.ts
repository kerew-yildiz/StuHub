import { authFetch } from './client'

export interface ChapterQuizQuestion {
  qid: string
  topic: string | null
  question: string
  options: string[]
  difficulty: string | null
}

export interface ChapterQuiz {
  id: number
  chapter_id: number
  created_at: string
  questions: ChapterQuizQuestion[]
}

export interface ChapterQuizResult {
  qid: string
  question: string
  selected_index: number
  correct_index: number
  correct: boolean
  explanation: string
  citations: unknown[]
  topic: string | null
}

export interface ChapterQuizAttempt {
  quiz_id: number
  score: number
  results: ChapterQuizResult[]
}

export async function listChapterQuizzes(chapterId: number): Promise<ChapterQuiz[]> {
  const response = await authFetch(`/chapters/${chapterId}/quizzes`)
  if (!response.ok) throw new Error('Chapter quizleri alınamadı.')
  return (await response.json()) as ChapterQuiz[]
}

export interface ChapterQuizGenerationResult {
  id: number
  question_count: number
}

/** §40 '+ Quiz Oluştur' — chapter için yeni quiz üretir. */
export async function generateChapterQuiz(chapterId: number): Promise<ChapterQuizGenerationResult> {
  const response = await authFetch(`/chapters/${chapterId}/quizzes/generate`, { method: 'POST' })
  if (!response.ok) {
    let detail = 'Quiz üretilemedi. Lütfen tekrar deneyin.'
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* varsayılan mesaj korunur */
    }
    throw new Error(detail)
  }
  return (await response.json()) as ChapterQuizGenerationResult
}

export async function submitChapterQuiz(quizId: number, answers: Array<{ qid: string; selected_index: number }>): Promise<ChapterQuizAttempt> {
  const response = await authFetch(`/quizzes/${quizId}/attempts`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  })
  if (!response.ok) throw new Error('Quiz değerlendirilemedi.')
  return (await response.json()) as ChapterQuizAttempt
}
