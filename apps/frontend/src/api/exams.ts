import { authFetch } from './client'
import type { OverallQuiz, OverallStreamHandlers } from './overall'

/** Sınav kaydı — backend `ExamOut` ile birebir (plan #9). */
export interface Exam {
  id: number
  course_id: number
  title: string
  /** ISO tarih, 'YYYY-MM-DD'. */
  exam_date: string
  /** Kapsam bölümleri; boş dizi = tüm ders. */
  chapter_ids: number[]
  /** Bugüne göre kalan gün; sınav geçmişse negatif. */
  days_left: number
  created_at: string
}

/** Yeni sınav gövdesi. */
export interface ExamInput {
  title: string
  /** ISO tarih, 'YYYY-MM-DD'. */
  exam_date: string
  chapter_ids?: number[]
}

/** Plandaki tek kart — cevap (`back`) alanı backend'den hiç gelmez. */
export interface PlanCard {
  set_id: number
  card_index: number
  topic: string
  front: string
}

/** Planın tek günü. */
export interface PlanDay {
  /** ISO tarih, 'YYYY-MM-DD'. */
  date: string
  card_count: number
  cards: PlanCard[]
}

/** Sınava kadarki günlük çalışma planı (`srs.compress_to_deadline` çıktısı). */
export interface ExamPlan {
  exam: Exam
  total_cards: number
  /** Yalnızca dolu günler, tarih sırasıyla; sınav gününe iş konmaz. */
  days: PlanDay[]
}

/** Unutma eğrisinin tek örneklem noktası. */
export interface RetentionPoint {
  /** Bugünden itibaren gün ofseti. */
  day: number
  /** Tahmini hatırlama oranı, 0..1. */
  retention: number
}

/** Bir konunun unutma eğrisi (plan #12). */
export interface TopicRetention {
  topic: string
  card_count: number
  reviewed_count: number
  /** Bugünkü tahmini hatırlama oranı, 0..1. */
  current: number
  points: RetentionPoint[]
}

/** Ders geneli unutma eğrisi — konular en zayıftan güçlüye sıralı gelir. */
export interface RetentionReport {
  course_id: number
  horizon_days: number
  generated_at: string
  topics: TopicRetention[]
}

/** Derse sınav ekler (POST /courses/{id}/exams). */
export async function createExam(courseId: number, input: ExamInput): Promise<Exam> {
  const response = await authFetch(`/courses/${courseId}/exams`, {
    method: 'POST',
    body: JSON.stringify({ chapter_ids: [], ...input }),
  })
  if (!response.ok) {
    throw new Error(
      response.status === 422
        ? 'Sınav kapsamındaki bölümler bu derse ait değil.'
        : 'Sınav eklenemedi. Lütfen tekrar deneyin.',
    )
  }
  return (await response.json()) as Exam
}

/** Dersin sınavları, tarihe göre yakından uzağa (GET /courses/{id}/exams). */
export async function listExams(courseId: number): Promise<Exam[]> {
  const response = await authFetch(`/courses/${courseId}/exams`)
  if (!response.ok) {
    throw new Error('Sınavlar alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as Exam[]
}

/** Sınav kaydını siler (DELETE /exams/{id}). */
export async function deleteExam(examId: number): Promise<void> {
  const response = await authFetch(`/exams/${examId}`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error('Sınav silinemedi. Lütfen tekrar deneyin.')
  }
}

/** Sınava kadarki günlük çalışma planı (GET /exams/{id}/plan). */
export async function getExamPlan(examId: number): Promise<ExamPlan> {
  const response = await authFetch(`/exams/${examId}/plan`)
  if (!response.ok) {
    throw new Error('Çalışma planı alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as ExamPlan
}

/** Konu bazlı unutma eğrisi (GET /courses/{id}/retention?days=N). */
export async function getRetention(courseId: number, days?: number): Promise<RetentionReport> {
  const suffix = days ? `?days=${days}` : ''
  const response = await authFetch(`/courses/${courseId}/retention${suffix}`)
  if (!response.ok) {
    throw new Error('Unutma eğrisi alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as RetentionReport
}

/** Sınav simülasyonunu başlatır — mevcut genel quiz motorunu `mode='exam'` ile çalıştırıp
 * SSE akışını okur (Plan #35). Dönen sorularda `correct_index`/`answer`/`accepted_answers`/
 * `feedback_*`/`explanation` YOKTUR — sonuç yalnızca `submitOverallAttempt` sonrasında görünür. */
export async function startExamSimulation(
  courseId: number,
  examId: number,
  handlers: OverallStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await authFetch(`/courses/${courseId}/exams/${examId}/simulate`, { method: 'POST' })
  } catch {
    handlers.onError?.('Sınav simülasyonu başlatılamadı. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Sınav simülasyonu başlatılamadı. Lütfen tekrar deneyin.')
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

/** Kaçırılan sorunun sebebi (Plan #44). */
export type PostmortemReason = 'bilmiyordum' | 'karıştırdım' | 'süre_yetmedi' | 'dikkatsizlik'

export interface PostmortemItem {
  question: string
  reason: PostmortemReason
}

/** Sınav sonrası muhasebe kaydı — backend `PostmortemOut` ile birebir (Plan #44). */
export interface Postmortem {
  exam_id: number
  items: PostmortemItem[]
  /** LLM'in ürettiği tek cümlelik çalışma tavsiyesi. */
  summary: string
  created_at: string
}

/** Kaçırılan soru + sebep listesini gönderir; backend LLM ile tek cümlelik özet üretir. */
export async function submitPostmortem(examId: number, items: PostmortemItem[]): Promise<Postmortem> {
  const response = await authFetch(`/exams/${examId}/postmortem`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  })
  if (!response.ok) {
    throw new Error('Muhasebe kaydedilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as Postmortem
}

/** Kayıtlı sınav sonrası muhasebeyi döner; hiç gönderilmemişse null. */
export async function getPostmortem(examId: number): Promise<Postmortem | null> {
  const response = await authFetch(`/exams/${examId}/postmortem`)
  if (response.status === 404) return null
  if (!response.ok) {
    throw new Error('Muhasebe kaydı alınamadı. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as Postmortem
}
