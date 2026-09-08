import { apiFetch } from './client'

/** Aksiyon türü — backend `NextActionOut.action` ile birebir. */
export type NextActionKind = 'cards' | 'error_quiz' | 'read_chapter' | 'none'

/** Tek karar önerisi (backend `NextActionOut` ile birebir, GET /courses/{id}/next-action).
 *
 * `target_id`: `action='cards'` için `flashcard_sets.id`, `action='read_chapter'` için
 * `chapters.id`; diğer aksiyonlarda `null`. */
export interface NextAction {
  action: NextActionKind
  reason: string
  target_id: number | null
}

/** Dersin deterministik "bugün ne çalışsam" önerisini çeker (Plan #13, LLM YOK). */
export function fetchNextAction(courseId: number): Promise<NextAction> {
  return apiFetch<NextAction>(`/courses/${courseId}/next-action`)
}
