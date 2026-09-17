import { authFetch } from './client'

/** Tamamlanmış bir pomodoro oturumu kaydı (backend `study_sessions` ile birebir). */
export interface StudySession {
  id: number
  course_id: number
  session_id: string
  duration_sec: number
  created_at: string
}

/** Ders bağlamı OLMAYAN kullanım oturumunu kaydeder (POST /study-sessions).
 *
 * Otomatik zaman takipleyici global sayfalarda geçen aktif süreyi bununla yazar. */
export async function createGlobalStudySession(
  sessionId: string,
  durationSec: number,
): Promise<StudySession> {
  const response = await authFetch('/study-sessions', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, duration_sec: durationSec }),
  })
  if (!response.ok) {
    throw new Error('Çalışma oturumu kaydedilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as StudySession
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

/** Chapter görünümünde geçen bir aralığı kaydeder
 * (POST /courses/{id}/chapters/{chapter_id}/study-time).
 *
 * `sessionId` (aralık UUID'si) bazında idempotenttir — ağ hatasında tekrar gönderim
 * süreyi çift saymaz. */
export async function sendStudyTimeHeartbeat(
  courseId: number,
  chapterId: number,
  sessionId: string,
  durationSec: number,
): Promise<void> {
  const response = await authFetch(`/courses/${courseId}/chapters/${chapterId}/study-time`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, duration_sec: durationSec }),
  })
  if (!response.ok) {
    throw new Error('Çalışma süresi kaydedilemedi. Lütfen tekrar deneyin.')
  }
}
