import { useEffect, useRef, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'

import {
  clearChat,
  listChat,
  streamChat,
  type ChatCitation,
  type ChatMessage,
  type ChatMode,
} from '../api/chat'
import type { Citation } from '../api/notes'
import { CitationPopup } from './CitationPopup'

interface ChatPanelProps {
  courseId: number
}

const CITATION_SCHEME = 'stuhub-chat-citation://'

const MODES: Array<{ value: ChatMode; label: string }> = [
  { value: 'direct', label: 'Doğrudan' },
  { value: 'socratic', label: 'Sokratik' },
  { value: 'quiz', label: 'Sınav Modu' },
]

/** `[n]` işaretlerini markdown bağlantısına çevirir: [1] → [1](stuhub-chat-citation://1) */
function enhanceMarkdown(body: string): string {
  return body.replace(/\[(\d+)\]/g, `[$1](${CITATION_SCHEME}$1)`)
}

/** Chat atıfını CitationPopup'un beklediği Citation biçimine eşler. */
function toPopupCitation(citation: ChatCitation): Citation {
  const label = citation.source_label ?? ''
  const sourceType: Citation['source_type'] = /sunum|slayt/i.test(label)
    ? 'slides'
    : /kitap/i.test(label)
      ? 'textbook'
      : citation.slide != null
        ? 'slides'
        : citation.page != null
          ? 'textbook'
          : 'note'
  return {
    id: citation.n,
    source_type: sourceType,
    source_id: null,
    page: citation.page,
    slide: citation.slide,
    chunk_id: citation.chunk_id,
    quote: '',
  }
}

function CitationLink({
  href,
  children,
  citations,
  onOpenCitation,
}: {
  href?: string
  children?: ReactNode
  citations: ChatCitation[]
  onOpenCitation: (citation: ChatCitation) => void
}) {
  if (href?.startsWith(CITATION_SCHEME)) {
    const n = Number(href.slice(CITATION_SCHEME.length))
    const citation = citations.find((c) => c.n === n)
    if (citation) {
      return (
        <button
          type="button"
          onClick={() => onOpenCitation(citation)}
          className="mx-1 inline-block rounded-chip bg-stuhub-accent/15 px-1 text-sm font-semibold text-stuhub-accent transition-colors duration-150 hover:bg-stuhub-accent/25"
          title="Atıf kaynağını göster"
        >
          [{n}]
        </button>
      )
    }
  }
  return <span>{children}</span>
}

function AssistantContent({
  content,
  citations,
  onOpenCitation,
}: {
  content: string
  citations: ChatCitation[]
  onOpenCitation: (citation: ChatCitation) => void
}) {
  return (
    <div className="text-sm leading-relaxed">
      <ReactMarkdown
        urlTransform={(url) => url}
        components={{
          a: ({ href, children }) => (
            <CitationLink
              href={href}
              children={children}
              citations={citations}
              onOpenCitation={onOpenCitation}
            />
          ),
          p: ({ children }) => <p className="my-1">{children}</p>,
          ul: ({ children }) => <ul className="mt-1 list-disc space-y-1 pl-6">{children}</ul>,
          ol: ({ children }) => <ol className="mt-1 list-decimal space-y-1 pl-6">{children}</ol>,
        }}
      >
        {enhanceMarkdown(content)}
      </ReactMarkdown>
    </div>
  )
}

/** "Materyale Sor" sohbet paneli — atıflı RAG chat (Faz 2.1). */
export function ChatPanel({ courseId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<ChatMode>('direct')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [streamCitations, setStreamCitations] = useState<ChatCitation[]>([])
  const [error, setError] = useState('')
  const [activeCitation, setActiveCitation] = useState<ChatCitation | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setMessages([])
    void listChat(courseId)
      .then((history) => {
        if (!cancelled) setMessages(history)
      })
      .catch(() => {
        if (!cancelled) setError('Sohbet geçmişi yüklenemedi.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, streamText])

  const handleSubmit = async () => {
    const text = input.trim()
    if (!text || sending) return
    setError('')
    setInput('')
    setSending(true)
    setStreaming(true)
    setStreamText('')
    setStreamCitations([])

    const userMessage: ChatMessage = {
      id: -Date.now(),
      role: 'user',
      content: text,
      mode,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])

    await streamChat(courseId, text, mode, {
      onCitations: (citations) => setStreamCitations(citations),
      onDelta: (delta) => setStreamText((prev) => prev + delta),
      onRetry: () => setStreamText(''), // ilk deneme iptal — metin sıfırlanır
      onDone: (message) => {
        setMessages((prev) => [...prev, message])
        setStreamText('')
        setStreamCitations([])
        setStreaming(false)
      },
      onError: (message) => {
        setError(message)
        setStreamText('')
        setStreamCitations([])
        setStreaming(false)
      },
    })
    setSending(false)
  }

  const handleClear = async () => {
    if (!window.confirm('Sohbet geçmişi silinecek. Emin misin?')) return
    try {
      await clearChat(courseId)
      setMessages([])
      setError('')
    } catch {
      setError('Sohbet geçmişi silinemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <div className="glass-panel p-5">
      <div className="flex items-center justify-between gap-4">
        <div
          className="glass-panel-subtle inline-flex max-w-full flex-wrap gap-1 p-1"
          role="group"
          aria-label="Yanıt modu"
        >
          {MODES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setMode(option.value)}
              aria-pressed={mode === option.value}
              className={`rounded-pill px-3.5 py-1.5 text-sm font-medium transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] active:scale-[0.98] ${
                mode === option.value
                  ? 'bg-stuhub-accent-glass border border-stuhub-accent-glass-border text-stuhub-text shadow-sm'
                  : 'border border-transparent text-stuhub-text-secondary hover:text-stuhub-text'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void handleClear()}
          className="rounded-control px-3 py-1 text-sm font-medium text-stuhub-error transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10"
        >
          Geçmişi Temizle
        </button>
      </div>

      <div ref={listRef} className="mt-4 max-h-96 space-y-3 overflow-y-auto">
        {loading && (
          <p className="text-sm text-stuhub-text-secondary">Yükleniyor…</p>
        )}
        {!loading && messages.length === 0 && !streaming && (
          <p className="text-sm text-stuhub-text-secondary">
            Materyale soru sorun — yanıtlar kaynak atıflı gelir.
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={
                message.role === 'user'
                  ? 'max-w-[80%] rounded-control bg-stuhub-accent-glass border border-stuhub-accent-glass-border px-4 py-2 text-sm text-stuhub-text'
                  : 'max-w-[80%] glass-panel-subtle px-4 py-2'
              }
            >
              {message.role === 'assistant' ? (
                <AssistantContent
                  content={message.content}
                  citations={message.citations_json ?? []}
                  onOpenCitation={setActiveCitation}
                />
              ) : (
                <span className="whitespace-pre-wrap">{message.content}</span>
              )}
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%] glass-panel-subtle px-4 py-2">
              {streamText ? (
                <AssistantContent
                  content={streamText}
                  citations={streamCitations}
                  onOpenCitation={setActiveCitation}
                />
              ) : (
                <span className="text-sm italic text-stuhub-text-secondary">Düşünüyor…</span>
              )}
            </div>
          </div>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
        >
          {error}
        </p>
      )}

      <div className="mt-4 flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleSubmit()
            }
          }}
          rows={2}
          placeholder="Materyale soru sorun…"
          className="flex-1 resize-none rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text placeholder:text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] focus:outline-none focus:border-stuhub-border-strong focus:ring-2 focus:ring-stuhub-accent-glass-border"
        />
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={sending || input.trim() === ''}
          className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100"
        >
          {sending ? 'Düşünüyor…' : 'Gönder'}
        </button>
      </div>

      {activeCitation && (
        <CitationPopup
          citation={toPopupCitation(activeCitation)}
          preloadedText={activeCitation.text}
          sourceLabel={activeCitation.source_label ?? undefined}
          onClose={() => setActiveCitation(null)}
        />
      )}
    </div>
  )
}
