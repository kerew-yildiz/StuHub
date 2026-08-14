import { BASE_URL } from './client'

/** Ödev değerlendirme ölçütü (backend ile birebir). */
export interface EssayCriterion {
  name: string
  score: number
  max: number
  comment: string
}

/** Öğrenci metninden alıntı + yorum. */
export interface EssayQuote {
  text: string
  comment: string
}

/** Ödev değerlendirme sonucu (score 0-100). */
export interface EssayGrade {
  score: number
  criteria: EssayCriterion[]
  strengths: string[]
  weaknesses: string[]
  quotes: EssayQuote[]
  confidence: number
}

/** Kayıtlı değerlendirme kaydı (geçmiş listesi). */
export interface EssayRecord {
  id: number
  course_id: number
  chapter_id: number | null
  prompt: string
  score: number
  created_at: string
}

/** 422 hata gövdesinden Türkçe `detail` mesajını çıkarır. */
async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) return body.detail
  } catch {
    // gövde JSON değilse fallback mesajı kullan
  }
  return fallback
}

/** Ödevi AI ile puanlar (POST /courses/{id}/essays/grade). */
export async function gradeEssay(
  courseId: number,
  instructions: string,
  rubric: string,
  userText: string,
): Promise<EssayGrade> {
  const body: { instructions: string; rubric?: string; user_text: string } = {
    instructions,
    user_text: userText,
  }
  const trimmedRubric = rubric.trim()
  if (trimmedRubric) body.rubric = trimmedRubric

  const response = await fetch(`${BASE_URL}/courses/${courseId}/essays/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(
      await readErrorDetail(response, 'Ödev değerlendirilemedi. Lütfen tekrar deneyin.'),
    )
  }
  return (await response.json()) as EssayGrade
}

/** Dersin ödev değerlendirme geçmişi (yeniden eskiye). */
export async function listEssays(courseId: number): Promise<EssayRecord[]> {
  const response = await fetch(`${BASE_URL}/courses/${courseId}/essays`)
  if (!response.ok) return []
  return (await response.json()) as EssayRecord[]
}
