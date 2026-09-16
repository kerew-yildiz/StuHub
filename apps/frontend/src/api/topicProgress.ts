import { apiFetch } from './client'

/** Chapter topic bazlı tamamlanma — GET /chapters/{id}/topic-progress.
 *
 * Konu listesindeki ilerleme çemberlerinin verisi: her topic için kart
 * tutma (good/easy SM-2) ve quiz doğruluk sinyallerinin ortalaması.
 * percent null → sinyal yok (çember boş çizilir, sahte yüzde üretilmez).
 */
export interface TopicProgress {
  topic: string
  percent: number | null
  cards_total: number
  cards_retained: number
  quiz_total: number
  quiz_correct: number
}

export interface TopicProgressReport {
  chapter_id: number
  topics: TopicProgress[]
  completed_topics: number
  total_topics: number
}

export function getTopicProgress(chapterId: number): Promise<TopicProgressReport> {
  return apiFetch<TopicProgressReport>(`/chapters/${chapterId}/topic-progress`)
}
