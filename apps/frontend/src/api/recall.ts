import { authFetch } from './client'

/** Konuşarak tekrar sonucu (Plan #47). */
export interface RecallResult {
  transcript: string
  covered_topics: string[]
  missed_topics: string[]
}

/** Ses kaydını yükler, mevcut notun konularıyla örtüşmesini döner
 * (POST /chapters/{id}/recall). LLM YOK — mevcut transkripsiyon zinciri kullanılır. */
export async function submitRecall(chapterId: number, audio: Blob): Promise<RecallResult> {
  const form = new FormData()
  form.append('file', audio, 'kayit.webm')
  const response = await authFetch(`/chapters/${chapterId}/recall`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail || 'Ses kaydı değerlendirilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as RecallResult
}
