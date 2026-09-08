import { Sparkle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { getRetentionProgress } from '../api/streaks'

export interface RetentionProgressBadgeProps {
  courseId: number
}

/** "Bu hafta N konuyu kalıcı hatırlama eşiğine taşıdın" rozeti (Plan #48).
 *
 * LLM YOK — `card_reviews` aralık eşiğinden (SM-2 interval_days >= 21) türetilir.
 * Hiç konu yoksa (ya da istek başarısızsa) sessizce gizlenir. */
export function RetentionProgressBadge({ courseId }: RetentionProgressBadgeProps) {
  const [count, setCount] = useState<number | null>(null)
  const [topics, setTopics] = useState<string[]>([])
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    void getRetentionProgress(courseId)
      .then((progress) => {
        if (cancelled) return
        setCount(progress.topics_mastered_this_week)
        setTopics(progress.topics)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  if (failed || !count) return null

  return (
    <div className="glass-panel-subtle flex items-center gap-2 rounded-control px-4 py-2 text-sm">
      <Sparkle size={18} weight="fill" className="shrink-0 text-stuhub-accent" />
      <span>
        Bu hafta <strong>{count}</strong> konuyu kalıcı hatırlama eşiğine taşıdın:{' '}
        {topics.join(', ')}
      </span>
    </div>
  )
}

export default RetentionProgressBadge
