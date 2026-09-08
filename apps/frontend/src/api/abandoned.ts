import { apiFetch } from './client'

/** Terk edilmiş tek konu satırı (backend `AbandonedTopic` ile birebir). */
export interface AbandonedTopic {
  topic: string
  chapter_id: number
  /** ISO zaman damgası; konu hiç çalışılmadıysa null. */
  last_activity: string | null
}

/** 3+ haftadır hiç aktivitesi olmayan konuları döner (Plan #50, LLM YOK). */
export function fetchAbandonedTopics(courseId: number): Promise<AbandonedTopic[]> {
  return apiFetch<AbandonedTopic[]>(`/courses/${courseId}/abandoned`)
}
