import { authFetch } from './client'

/** Tamamlanmış bir pomodoro oturumu kaydı (backend `study_sessions` ile birebir). */
export interface StudySession {
  id: number
  course_id: number
  session_id: string
  duration_sec: number
  created_at: string
}

/** Tamamlanmış bir çalışma oturumunu kaydeder (POST /courses/{id}/study-sessions).
 *
 * `sessionId` bazında idempotenttir — ağ hatasında yeniden gönderilirse aynı oturum
 * iki kez kaydedilmez, mevcut kayıt döner (Plan #14). */
export async function createStudySession(
  courseId: number,
  sessionId: string,
  durationSec: number,
): Promise<StudySession> {
  const response = await authFetch(`/courses/${courseId}/study-sessions`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, duration_sec: durationSec }),
  })
  if (!response.ok) {
    throw new Error('Çalışma oturumu kaydedilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as StudySession
}
