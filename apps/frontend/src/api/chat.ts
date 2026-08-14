import { BASE_URL } from './client'

/** Sohbet modu (backend sözleşmesi: direct | socratic | quiz). */
export type ChatMode = 'direct' | 'socratic' | 'quiz'

/** Atıf kaydı — backend `citations` event'i ve `citations_json` ile birebir. */
export interface ChatCitation {
  n: number
  chunk_id: string | null
  text: string
  page: number | null
  slide: number | null
  source_label: string | null
}

/** Sohbet mesajı (kullanıcı veya asistan). */
export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  citations_json?: ChatCitation[]
  mode: ChatMode
  created_at: string
}

export interface ChatStreamHandlers {
  onCitations?: (citations: ChatCitation[]) => void
  onDelta?: (text: string) => void
  onRetry?: (message: string) => void
  onDone?: (message: ChatMessage) => void
  onError?: (message: string) => void
}

interface ChatStreamEvent {
  type: string
  citations?: ChatCitation[]
  text?: string
  message?: ChatMessage | string
}

/** Sohbeti POST edip SSE akışını okur (Faz 2.1 — atıflı RAG chat). */
export async function streamChat(
  courseId: number,
  message: string,
  mode: ChatMode,
  handlers: ChatStreamHandlers,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}/courses/${courseId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode }),
    })
  } catch {
    handlers.onError?.('Mesaj gönderilemedi. Lütfen tekrar deneyin.')
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError?.('Mesaj gönderilemedi. Lütfen tekrar deneyin.')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const chunk = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '))
        if (!dataLine) continue
        let event: ChatStreamEvent
        try {
          event = JSON.parse(dataLine.slice(6)) as ChatStreamEvent
        } catch {
          continue
        }
        if (event.type === 'citations' && event.citations) {
          handlers.onCitations?.(event.citations)
        } else if (event.type === 'delta' && typeof event.text === 'string') {
          handlers.onDelta?.(event.text)
        } else if (event.type === 'retry') {
          handlers.onRetry?.(
            typeof event.message === 'string' ? event.message : 'Yanıt yeniden üretiliyor…',
          )
        } else if (event.type === 'done' && event.message && typeof event.message !== 'string') {
          handlers.onDone?.(event.message)
        } else if (event.type === 'error') {
          handlers.onError?.(
            typeof event.message === 'string' ? event.message : 'Yanıt üretilemedi.',
          )
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Dersin sohbet geçmişini döndürür (kronolojik, son 100). */
export async function listChat(courseId: number): Promise<ChatMessage[]> {
  try {
    const response = await fetch(`${BASE_URL}/courses/${courseId}/chat`)
    if (!response.ok) return []
    const body = (await response.json()) as { messages?: ChatMessage[] }
    return body.messages ?? []
  } catch {
    return []
  }
}

/** Dersin sohbet geçmişini temizler (DELETE → 204). */
export async function clearChat(courseId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/courses/${courseId}/chat`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error('Sohbet geçmişi silinemedi.')
  }
}
