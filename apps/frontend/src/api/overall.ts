import { BASE_URL } from './client'

/** Genel quiz veri modelleri (backend ile birebir; answer_key'ler frontend'e gelmez). */
export interface OverallCitation {
  id: number
  source_type: 'textbook' | 'slides' | 'note'
  source_id: number | null
  page: number | null
  slide: number | null
  chunk_id: string | null
  quote: string
}

export interface OverallQuestion {
  type: 'mcq' | 'tf' | 'fib' | 'open'
  topic: string
  question?: string
  options?: string[]
  correct_index?: number
  statement?: string
  answer?: boolean
  text?: string
  accepted_answers?: string[]
  explanation: string
  feedback_correct?: string
  feedback_wrong?: string
  citations: OverallCitation[]
  answer_key_ref?: string
}

export interface OverallQuiz {
  id: number
  course_id: number
  questions_json: { seed: number; questions: OverallQuestion[] }
}

export interface OverallGrade {
  correct: string[]
  missing: string[]
  incorrect: string[]
  unnecessary: string[]
  explanation: string
  ideal_answer: string
}

export interface OverallResult {
  qid: number
  type: string
  question: string
  correct?: boolean
  feedback?: string
  explanation?: string
  citations?: OverallCitation[]
  accepted_answers?: string[]
  score?: number
  grade?: OverallGrade
}

export interface OverallOutcome {
  attempt_id: number
  score: number
  closed_correct: number
  closed_total: number
  open_total: number
  results: OverallResult[]
}

export interface OverallStreamHandlers {
  onStatus?: (percent: number, message: string) => void
  onDone?: (quiz: OverallQuiz) => void
  onError?: (message: string) => void
}

/** Genel quiz üretimini POST edip SSE akışını okur (Faz 5.1). */
export async function streamOverallQuizGeneration(
  courseId: number,
  handlers: OverallStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/courses/${courseId}/overall-quiz`, { method: 'POST' })
  } catch {
    handlers.onError?.('Genel quiz üretimi başlatılamadı. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Genel quiz üretimi başlatılamadı. Lütfen tekrar deneyin.')
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
        let event: { type: string; percent?: number; message?: string; quiz?: OverallQuiz }
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

/** Dersin en güncel genel quizi (answer_key'siz). */
export async function getOverallQuiz(courseId: number): Promise<OverallQuiz | null> {
  const response = await fetch(`${BASE_URL}/courses/${courseId}/overall-quiz`)
  if (!response.ok) return null
  return (await response.json()) as OverallQuiz
}

/** Tüm cevapları gönderir; kapalı sorular anında, açık uçlular Essay Grader ile puanlanır. */
export async function submitOverallAttempt(
  quizId: number,
  answers: Array<{ qid: number; value: number | string }>,
): Promise<OverallOutcome> {
  const response = await fetch(`${BASE_URL}/overall-quizzes/${quizId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
  if (!response.ok) {
    throw new Error('Cevaplar gönderilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as OverallOutcome
}
