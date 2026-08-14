import { BASE_URL } from './client'

/** Quiz veri modelleri (backend ile birebir). */
export interface QuizCitation {
  id: number
  source_type: 'textbook' | 'slides' | 'note'
  source_id: number | null
  page: number | null
  slide: number | null
  chunk_id: string | null
  quote: string
}

export interface QuizQuestion {
  topic: string
  question: string
  options: string[]
  correct_index: number
  explanation: string
  feedback_correct: string
  feedback_wrong: string
  citations: QuizCitation[]
}

export interface Quiz {
  id: number
  chapter_id: number
  questions_json: { topics: Array<{ topic: string; questions: QuizQuestion[] }> }
}

export interface AttemptResult {
  qid: string
  question: string
  selected_index: number
  correct_index: number
  correct: boolean
  feedback: string
  explanation: string
  citations: QuizCitation[]
  options: string[]
}

export interface AttemptOutcome {
  attempt_id: number
  score: number
  total: number
  correct_count: number
  results: AttemptResult[]
}

export interface FlatQuestion {
  qid: string
  question: QuizQuestion
}

/** Soruları qid'li düz listeye çevirir (qid = '<topic_idx>-<q_idx>'). */
export function flattenQuestions(quiz: Quiz): FlatQuestion[] {
  const flattened: FlatQuestion[] = []
  quiz.questions_json.topics.forEach((topic, tIdx) => {
    topic.questions.forEach((question, qIdx) => {
      flattened.push({ qid: `${tIdx}-${qIdx}`, question })
    })
  })
  return flattened
}

export interface QuizStreamHandlers {
  onStatus?: (percent: number, message: string) => void
  onDone?: (quiz: Quiz) => void
  onError?: (message: string) => void
}

/** Quiz üretimini POST edip SSE akışını okur (Faz 4.1). */
export async function streamQuizGeneration(
  chapterId: number,
  handlers: QuizStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/chapters/${chapterId}/quiz`, { method: 'POST' })
  } catch {
    handlers.onError?.('Quiz üretimi başlatılamadı. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Quiz üretimi başlatılamadı. Lütfen tekrar deneyin.')
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
        let event: { type: string; percent?: number; message?: string; quiz?: Quiz }
        try {
          event = JSON.parse(dataLine.slice(6))
        } catch {
          continue
        }
        if (event.type === 'status') {
          handlers.onStatus?.(event.percent ?? 0, event.message ?? '')
        } else if (event.type === 'done' && event.quiz) {
          handlers.onDone?.(event.quiz)
        } else if (event.type === 'error') {
          handlers.onError?.(event.message ?? 'Üretim başarısız oldu.')
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Chapter'ın en güncel quizi. */
export async function getQuiz(chapterId: number): Promise<Quiz | null> {
  const response = await fetch(`${BASE_URL}/chapters/${chapterId}/quiz`)
  if (!response.ok) return null
  return (await response.json()) as Quiz
}

/** Cevapları gönderir; anında feedback döner (backend'de LLM çağrısı yok). */
export async function submitAttempt(
  quizId: number,
  answers: Array<{ qid: string; selected_index: number }>,
): Promise<AttemptOutcome> {
  const response = await fetch(`${BASE_URL}/quizzes/${quizId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
  if (!response.ok) {
    throw new Error('Cevap gönderilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as AttemptOutcome
}
