import { apiFetch } from './client'

/** Streak özeti (backend GET /api/streaks ile birebir). */
export interface StreakSummary {
  streak_days: number
  today_counts: {
    note: number
    quiz: number
    flashcard: number
    chat: number
  }
  daily_goal: number
  /** 0–100 arası, tavanlı (hedef aşılsa bile 100'de durur). */
  progress_percent: number
}

/** Günlük streak + hedef özetini çeker (YETENEKLER/15). */
export function getStreakSummary(): Promise<StreakSummary> {
  return apiFetch<StreakSummary>('/streaks')
}
