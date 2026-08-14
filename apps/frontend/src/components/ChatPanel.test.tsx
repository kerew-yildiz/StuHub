import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ChatMessage } from '../api/chat'
import { ChatPanel } from './ChatPanel'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

/** SSE olaylarını tek bir ReadableStream'e dizen yardımcı. */
function encodeSSE(events: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${event}\n\n`))
      }
      controller.close()
    },
  })
}

/** global.fetch'i GET (geçmiş) + POST (SSE) + DELETE (temizle) için taklit eder. */
function stubChatFetch(opts: { history?: ChatMessage[]; stream?: string[] } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (init?.method === 'POST' && url.endsWith('/chat')) {
      return new Response(encodeSSE(opts.stream ?? []), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }
    if (init?.method === 'DELETE') {
      return new Response(null, { status: 204 })
    }
    return new Response(JSON.stringify({ messages: opts.history ?? [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const history: ChatMessage[] = [
  {
    id: 1,
    role: 'user',
    content: 'Fosfolipid nedir?',
    mode: 'direct',
    created_at: '2026-08-14T10:00:00Z',
  },
  {
    id: 2,
    role: 'assistant',
    content: 'Fosfolipid çift katman oluşturur [1].',
    citations_json: [
      {
        n: 1,
        chunk_id: 'chk_1',
        text: 'Fosfolipidler iki katmanlı yapı oluşturur.',
        page: 41,
        slide: null,
        source_label: 'Kitap s.41',
      },
    ],
    mode: 'direct',
    created_at: '2026-08-14T10:00:01Z',
  },
]

describe('ChatPanel', () => {
  it('geçmiş mesajları render eder', async () => {
    stubChatFetch({ history })
    render(<ChatPanel courseId={1} />)

    expect(await screen.findByText('Fosfolipid nedir?')).toBeInTheDocument()
    const matches = screen.getAllByText(
      (_, element) => element?.textContent?.includes('Fosfolipid çift katman oluşturur') ?? false,
    )
    expect(matches.length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: '[1]' })).toBeInTheDocument()
  })

  it('gönderince input temizlenir ve kullanıcı mesajı listeye düşer', async () => {
    stubChatFetch({
      stream: [
        JSON.stringify({
          type: 'citations',
          citations: [
            {
              n: 1,
              chunk_id: 'chk_1',
              text: 'Fosfolipidler iki katmanlı yapı oluşturur.',
              page: 41,
              slide: null,
              source_label: 'Kitap s.41',
            },
          ],
        }),
        JSON.stringify({ type: 'delta', text: 'Yanıt ' }),
        JSON.stringify({ type: 'delta', text: 'metni' }),
        JSON.stringify({
          type: 'done',
          message: {
            id: 2,
            role: 'assistant',
            content: 'Yanıt metni',
            citations_json: [],
            mode: 'direct',
            created_at: '2026-08-14T10:00:00Z',
          },
        }),
      ],
    })
    render(<ChatPanel courseId={1} />)
    await screen.findByText('Materyale soru sorun — yanıtlar kaynak atıflı gelir.')

    const textarea = screen.getByPlaceholderText('Materyale soru sorun…')
    fireEvent.change(textarea, { target: { value: 'Fosfolipid nedir?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Gönder' }))

    expect(await screen.findByText('Fosfolipid nedir?')).toBeInTheDocument()
    expect(textarea).toHaveValue('')
    expect(await screen.findByText('Yanıt metni')).toBeInTheDocument()
  })

  it('mod seçici değişince aktif sınıf güncellenir', async () => {
    stubChatFetch()
    render(<ChatPanel courseId={1} />)
    await screen.findByText('Materyale soru sorun — yanıtlar kaynak atıflı gelir.')

    const socratic = screen.getByRole('button', { name: 'Sokratik' })
    expect(socratic).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(socratic)
    expect(socratic).toHaveAttribute('aria-pressed', 'true')
    expect(socratic.className).toContain('bg-stuhub-accent')
    expect(screen.getByRole('button', { name: 'Doğrudan' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})
