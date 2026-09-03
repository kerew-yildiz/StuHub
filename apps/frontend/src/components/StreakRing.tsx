import { Flame } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { getStreakSummary, type StreakSummary } from '../api/streaks'

/** SVG ilerleme halkası — çevresi progress_percent ile dolar; renkler theme token'larından. */
function ProgressRing({ percent }: { percent: number }) {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const clamped = Math.min(Math.max(percent, 0), 100)
  const offset = circumference - (clamped / 100) * circumference

  return (
    <svg
      width="96"
      height="96"
      viewBox="0 0 96 96"
      role="img"
      aria-label={`Günlük hedef ilerlemesi %${Math.round(clamped)}`}
      className="shrink-0"
    >
      <circle
        cx="48"
        cy="48"
        r={radius}
        fill="none"
        stroke="var(--stuhub-border)"
        strokeWidth="8"
      />
      <circle
        cx="48"
        cy="48"
        r={radius}
        fill="none"
        stroke="var(--stuhub-accent)"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 48 48)"
        className="transition-[stroke-dashoffset] duration-150 ease-out"
      />
      <text
        x="48"
        y="48"
        textAnchor="middle"
        dominantBaseline="central"
        fill="var(--stuhub-text)"
        className="text-lg font-semibold"
      >
        {Math.round(clamped)}%
      </text>
    </svg>
  )
}

/** Streak özet kartı — halka + "🔥 X gün streak" + günlük etkinlik sayısı (Faz V2.4). */
export function StreakRing() {
  const [summary, setSummary] = useState<StreakSummary | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getStreakSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (failed) return null

  const todayTotal = summary
    ? summary.today_counts.note +
      summary.today_counts.quiz +
      summary.today_counts.flashcard +
      summary.today_counts.chat
    : 0

  return (
    <div className="glass-panel p-5">
      {summary ? (
        <div className="flex items-center gap-5">
          <ProgressRing percent={summary.progress_percent} />
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-lg font-semibold">
              <Flame weight="fill" className="h-5 w-5 shrink-0 text-stuhub-warning" aria-hidden="true" />
              {summary.streak_days} gün streak
            </p>
            {todayTotal > 0 ? (
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Bugün {todayTotal}/{summary.daily_goal} etkinlik
              </p>
            ) : (
              <p className="mt-1 text-sm text-stuhub-text-secondary">
                Bugün ilk etkinliğini yap — not üret, quiz çöz ya da kart tekrarla.
              </p>
            )}
          </div>
        </div>
      ) : (
        <p className="text-sm text-stuhub-text-secondary">Streak yükleniyor…</p>
      )}
    </div>
  )
}
