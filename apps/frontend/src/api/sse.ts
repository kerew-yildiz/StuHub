/** SSE yardımcısı — not üretimi akışı için (Faz 3'te kullanılacak). */

export interface SSEHandlers {
  onMessage?: (event: MessageEvent<string>) => void
  onError?: (event: Event) => void
  onOpen?: () => void
}

/** EventSource bağlantısı kurar; dönüş değeri kapatmak için saklanır. */
export function connectSSE(url: string, handlers: SSEHandlers): EventSource {
  const source = new EventSource(url)
  if (handlers.onOpen) source.onopen = handlers.onOpen
  if (handlers.onError) source.onerror = handlers.onError
  if (handlers.onMessage) source.onmessage = handlers.onMessage
  return source
}
