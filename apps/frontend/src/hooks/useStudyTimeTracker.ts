import { useEffect, useRef } from 'react'

import { createGlobalStudySession, createStudySession } from '../api/studySessions'

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
 */

const BLOCK_SEC = 5 * 60
const ACTIVITY_WINDOW_MS = 90_000

export function useStudyTimeTracker(courseId?: number): void {
  const lastActivityRef = useRef<number>(Date.now())
  const accumulatedRef = useRef(0)
  const courseIdRef = useRef<number | undefined>(courseId)

  courseIdRef.current = courseId

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

    const tick = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (Date.now() - lastActivityRef.current > ACTIVITY_WINDOW_MS) return
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
