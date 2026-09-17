import { useEffect, useRef } from 'react'
import { useMatch } from 'react-router-dom'

import {
  createGlobalStudySession,
  createStudySession,
  sendStudyTimeHeartbeat,
} from '../api/studySessions'

/**
 * Otomatik çalışma süresi takipleyici (sıkıntı kaydı #2).
 *
 * Kullanıcı uygulamada "aktif" kaldığı süreyi ölçer ve 5 dakikalık bloklar
 * hâlinde backend'e kaydeder. Aktiflik: sekme görünür (visibilitychange) VE
 * son 90 sn içinde kullanıcı etkileşimi (click/keydown/pointerdown/scroll).
 *
 * - courseId verilirse POST /courses/{id}/study-sessions, yoksa POST /study-sessions.
 * - Kayıt idempotent (session_id bazlı) — sekme kapanırken/kaybedilirken yarıda
 *   kalan blok kaybolur, mükerrer kayıt oluşmaz.
 * - Sekme gizlenince görünürlük süresi durur; döndüğünde kaldığı yerden ölçer.
 *
 * Chapter görünümünde (/dersler/:courseId/defter/:chapterId) süre ders+chapter
 * bazında sayılır: 45 sn'lik aralıklar heartbeat olarak gönderilir
 * (POST /courses/{id}/chapters/{chapter_id}/study-time, `session_id` bazında
 * idempotent). Bu sırada global blok sayacı işlemez — aynı saniyeler hem chapter
 * hem uygulama toplamına yazılmaz. Chapter değişince yarım aralık sıfırlanır:
 * en fazla son yarım aralık kaybolur (heartbeat toleransı).
 */

const BLOCK_SEC = 5 * 60
const HEARTBEAT_SEC = 45
const ACTIVITY_WINDOW_MS = 90_000

export function useStudyTimeTracker(courseId?: number): void {
  const lastActivityRef = useRef<number>(Date.now())
  const accumulatedRef = useRef(0)
  const courseIdRef = useRef<number | undefined>(courseId)
  const heartbeatRef = useRef(0)

  courseIdRef.current = courseId

  const match = useMatch('/dersler/:courseId/defter/:chapterId')
  const urlCourseId = Number(match?.params.courseId)
  const chapterId = Number(match?.params.chapterId)
  const chapter =
    Number.isFinite(urlCourseId) && Number.isFinite(chapterId)
      ? { courseId: urlCourseId, chapterId }
      : null
  const chapterRef = useRef<{ courseId: number; chapterId: number } | null>(null)
  chapterRef.current = chapter

  // Chapter değişimi (giriş/çıkış/başka chapter) yarım aralığı sıfırlar — süre
  // yanlış chapter'a yazılmaz.
  const chapterKey = chapter ? `${chapter.courseId}:${chapter.chapterId}` : ''
  useEffect(() => {
    heartbeatRef.current = 0
  }, [chapterKey])

  useEffect(() => {
    if (document.visibilityState === 'visible') {
      lastActivityRef.current = Date.now()
    }

    const markActivity = () => {
      lastActivityRef.current = Date.now()
    }

    const flush = async () => {
      const seconds = accumulatedRef.current
      if (seconds <= 0) return
      accumulatedRef.current = 0
      const sessionId = crypto.randomUUID()
      const cid = courseIdRef.current
      try {
        if (cid != null) await createStudySession(cid, sessionId, seconds)
        else await createGlobalStudySession(sessionId, seconds)
      } catch {
        // Sessiz: takip arka plan özelliği, kullanıcıya hata gösterilmez.
      }
    }

    const sendHeartbeat = async (
      target: { courseId: number; chapterId: number },
      seconds: number,
    ) => {
      try {
        await sendStudyTimeHeartbeat(
          target.courseId,
          target.chapterId,
          crypto.randomUUID(),
          seconds,
        )
      } catch {
        // Sessiz: takip arka plan özelliği, kullanıcıya hata gösterilmez.
      }
    }

    const tick = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (Date.now() - lastActivityRef.current > ACTIVITY_WINDOW_MS) return
      const current = chapterRef.current
      if (current) {
        heartbeatRef.current += 1
        if (heartbeatRef.current >= HEARTBEAT_SEC) {
          const seconds = heartbeatRef.current
          heartbeatRef.current = 0
          void sendHeartbeat(current, seconds)
        }
        return
      }
      accumulatedRef.current += 1
      if (accumulatedRef.current >= BLOCK_SEC) void flush()
    }, 1000)

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        lastActivityRef.current = Date.now()
      } else {
        // Sekme gizlenirken yarım kalan süreyi koru — dönünce devam eder.
        void flush()
      }
    }

    const activityEvents: Array<keyof DocumentEventMap> = [
      'click',
      'keydown',
      'pointerdown',
      'scroll',
      'touchstart',
    ]
    activityEvents.forEach((event) =>
      document.addEventListener(event, markActivity, { passive: true }),
    )
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      window.clearInterval(tick)
      activityEvents.forEach((event) => document.removeEventListener(event, markActivity))
      document.removeEventListener('visibilitychange', onVisibility)
      void flush()
    }
  }, [])
}
