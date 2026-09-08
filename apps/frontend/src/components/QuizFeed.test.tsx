import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authFetch } from '../api/client'
import type { AnswerResult, FeedBatch, FeedQuestion } from '../api/feed'
import { useFeedStore } from '../stores/feedStore'
import { QuizFeed } from './QuizFeed'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, authFetch: vi.fn() }
})

/** jsdom'da IntersectionObserver yok — kart saptama testte store üzerinden sürülür. */
class IntersectionObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): [] {
    return []
  }
}
vi.stubGlobal('IntersectionObserver', IntersectionObserverStub)

const mockFetch = vi.mocked(authFetch)

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response
}

function batch(startId: number, count: number, extra: Partial<FeedBatch> = {}): FeedBatch {
  const items: FeedQuestion[] = Array.from({ length: count }, (_, i) => ({
    feed_id: startId + i,
    question: `Soru ${startId + i}?`,
    options: ['A', 'B', 'C', 'D'],
    topic: 'Konu A',
    chapter_id: 1,
    difficulty: 'medium',
  }))
  return { items, pool_ready: 25, generating: false, ...extra }
}

/** Yalnızca feed parti isteklerini sayar (cevap/atlama POST'ları hariç). */
function feedCalls(): string[] {
  return mockFetch.mock.calls.map((call) => String(call[0])).filter((path) => path.includes('/feed?'))
}

/** Mikrogörev kuyruğunu boşaltır — sıkı döngü olsaydı burada patlardı. */
async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
  })
}

beforeEach(() => {
  useFeedStore.getState().reset()
  mockFetch.mockReset()
})

afterEach(() => {
  cleanup()
  useFeedStore.getState().reset()
})

describe('QuizFeed', () => {
  it('ilk yükte 5 soru ister ve ilk kartı gösterir', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 5)))

    render(<QuizFeed courseId={7} />)

    expect(await screen.findByText('Soru 1?')).toBeInTheDocument()
    expect(feedCalls()).toEqual(['/courses/7/feed?limit=5'])
    // Pencereleme: aktif kart + 1 alt mount, gerisi boş yuva
    expect(screen.getByText('Soru 2?')).toBeInTheDocument()
    expect(screen.queryByText('Soru 3?')).not.toBeInTheDocument()
    // Cevaplanmadan doğru cevap bilgisi DOM'a girmez
    expect(screen.queryByText('Doğru!')).not.toBeInTheDocument()
    expect(screen.queryByText('Yanlış')).not.toBeInTheDocument()
  })

  it('aktif soruyla etkileşime girmeden sıradaki soruya geçilemez', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 5)))
    render(<QuizFeed courseId={7} />)
    await screen.findByText('Soru 1?')

    // Cevaplamadan/atlamadan ileri kaydırma denemesi reddedilir.
    await act(async () => useFeedStore.getState().setIndex(1))
    expect(useFeedStore.getState().index).toBe(0)

    // Etkileşim (cevap/atla) işaretlenince artık ilerlenebilir; tampon eksiği de tamamlanır.
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(6, 1)))
    useFeedStore.setState((state) => ({ interacted: { ...state.interacted, [1]: true } }))
    await act(async () => useFeedStore.getState().setIndex(1))
    expect(useFeedStore.getState().index).toBe(1)
    await flush()
    expect(feedCalls()).toHaveLength(2)
  })

  it('bir soruyla etkileşime girilince tampon eksik kadar tamamlanır (azami 5)', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 5)))
    render(<QuizFeed courseId={7} />)
    await screen.findByText('Soru 1?')
    expect(feedCalls()).toHaveLength(1)

    // 5 soru sırada (index 0, hiçbiri etkileşim görmedi) → deficit 0, ek istek yok.
    await flush()
    expect(feedCalls()).toHaveLength(1)

    // Soru 1'i cevaplayınca tampon 4'e iner → eksik olan 1 soru arka planda çekilir.
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ correct: true, correct_index: 0, explanation: '', citations: null, note_id: null, chapter_id: null }),
    )
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(6, 1)))
    await act(async () => useFeedStore.getState().submitAnswer(1, 0, 100))
    await flush()

    expect(feedCalls()).toHaveLength(2)
    expect(feedCalls().at(-1)).toBe('/courses/7/feed?limit=1')
    expect(useFeedStore.getState().queue).toHaveLength(6)
  })

  it('atla, tampon eş zamanlı tamamlansa bile sadece bir sonraki soruya geçer', async () => {
    // 2026-09-08 canlı bulgu: "Atla" sonrası tampon tamamlama isteği (ensureBuffer)
    // ile goTo() aynı anda tetiklenince, IntersectionObserver'ın her tampon
    // güncellemesinde yeniden kurulması index'i en son eklenen soruya kaydırıyordu.
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 5)))
    render(<QuizFeed courseId={7} />)
    await screen.findByText('Soru 1?')

    // skipQuestion() önce ensureBuffer()'ı (senkron tetiklenen GET .../feed) çağırır,
    // `await skipFeed(...)` (POST .../feed/skip) ondan SONRA başlar — mock sırası buna göre.
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(6, 1))) // tampon tamamlama
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true })) // POST .../feed/skip

    const card = within(screen.getByLabelText('Soru 1'))
    fireEvent.click(card.getByRole('button', { name: 'Atla' }))
    await flush()

    expect(useFeedStore.getState().index).toBe(1)
    expect(useFeedStore.getState().queue).toHaveLength(6)
  })

  it('cevap sonrası sunucudan gelen geri bildirimi gösterir', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 10)))
    render(<QuizFeed courseId={7} />)
    await screen.findByText('Soru 1?')

    const result: AnswerResult = {
      correct: false,
      correct_index: 2,
      explanation: 'Doğru cevap C, çünkü tanım gereği böyle.',
      citations: [
        {
          id: 1,
          source_type: 'textbook',
          source_id: 9,
          page: 41,
          slide: null,
          chunk_id: 'chk_1_9_3',
          quote: 'kaynak alıntısı',
        },
      ],
      note_id: 5,
      chapter_id: 1,
    }
    mockFetch.mockResolvedValueOnce(jsonResponse(result))

    const card = within(screen.getByLabelText('Soru 1'))
    fireEvent.click(card.getByRole('button', { name: 'B' }))

    expect(await screen.findByText('Yanlış')).toBeInTheDocument()
    expect(screen.getByText('Doğru cevap C, çünkü tanım gereği böyle.')).toBeInTheDocument()
    expect(screen.getByText('sayfa 41')).toBeInTheDocument()
    expect(mockFetch).toHaveBeenLastCalledWith(
      '/feed/1/answer',
      expect.objectContaining({ method: 'POST' }),
    )
    const body = JSON.parse(String(mockFetch.mock.calls.at(-1)?.[1]?.body)) as {
      selected_index: number
      elapsed_ms: number
    }
    expect(body.selected_index).toBe(1)
    expect(typeof body.elapsed_ms).toBe('number')
  })

  it('boş parti + generating durumunda hazırlanıyor gösterir, istek döngüsü patlamaz', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ items: [], pool_ready: 0, generating: true }))

    render(<QuizFeed courseId={3} />)

    expect(await screen.findByText('Yeni sorular hazırlanıyor…')).toBeInTheDocument()
    await flush()
    await flush()
    expect(feedCalls()).toHaveLength(1)
    expect(useFeedStore.getState().phase).toBe('waiting')
  })

  it('havuz boşken üstel geri çekilmeyle yeniden dener (3 sn, sonra 6 sn)', async () => {
    vi.useFakeTimers()
    try {
      mockFetch.mockResolvedValue(jsonResponse({ items: [], pool_ready: 0, generating: true }))

      await act(async () => {
        await useFeedStore.getState().loadInitial(4)
      })
      expect(feedCalls()).toHaveLength(1)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(feedCalls()).toHaveLength(2)

      // sonraki gecikme 6 sn: 3 sn'de tetiklenmez
      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
      })
      expect(feedCalls()).toHaveLength(2)

      await act(async () => {
        vi.advanceTimersByTime(3000)
        await Promise.resolve()
        await Promise.resolve()
        await Promise.resolve()
      })
      expect(feedCalls()).toHaveLength(3)
    } finally {
      vi.useRealTimers()
    }
  })

  it('ağ hatasında kuyruk korunur ve Türkçe hata durumu yayınlanır', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(batch(1, 5)))
    render(<QuizFeed courseId={7} />)
    await screen.findByText('Soru 1?')

    mockFetch.mockRejectedValueOnce(new Error('offline'))
    await act(async () => useFeedStore.getState().retry())
    await flush()

    const state = useFeedStore.getState()
    expect(state.queue).toHaveLength(5)
    expect(state.phase).toBe('error')
    expect(state.error).toBe('Sorular alınamadı. Bağlantını kontrol et.')
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()
  })
})
