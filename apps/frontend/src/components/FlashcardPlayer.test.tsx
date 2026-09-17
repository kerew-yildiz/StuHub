import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as flashcardsModule from '../api/flashcards'
import { submitReview, type DueCard } from '../api/flashcards'
import { FlashcardPlayer } from './FlashcardPlayer'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

vi.mock('../api/flashcards', async (importOriginal) => {
  const actual = await importOriginal<typeof flashcardsModule>()
  return {
    ...actual,
    submitReview: vi.fn(async () => ({
      set_id: 1,
      card_index: 0,
      ease_factor: 2.5,
      interval_days: 1,
      repetitions: 0,
      due_at: '2026-08-15T09:00:00Z',
      last_rating: 'again',
    })),
  }
})

const dueCards: DueCard[] = [
  {
    set_id: 1,
    card_index: 0,
    card: {
      topic: 'Konu A',
      front: 'Soru 1?',
      back: 'Cevap 1',
      type: 'qa',
      citations: [],
    },
    review: null,
    due: true,
  },
  {
    set_id: 1,
    card_index: 1,
    card: {
      topic: 'Konu A',
      front: 'Soru 2?',
      back: 'Cevap 2',
      type: 'qa',
      citations: [],
    },
    review: null,
    due: true,
  },
]

/** Kart grubunu (swipe/klavye hedefi) bulur. */
function getCardGroup() {
  return screen.getByRole('group', { name: /Flashcard/ })
}

/** jsdom'da PointerEvent yok: tipi pointer olan MouseEvent gerçek koordinatlarla gönderilir. */
function pointer(tip: string, x: number, y: number) {
  return new MouseEvent(tip, { clientX: x, clientY: y, bubbles: true, cancelable: true })
}

describe('FlashcardPlayer', () => {
  it('ön yüzü gösterir ve tıklayınca arka yüzü çevirir', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    expect(screen.queryByText('Cevap 1')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))

    expect(screen.getByText('Cevap 1')).toBeInTheDocument()
    // §42 swipe modeli: yön ipuçları görünür, buton grid'i YOK
    expect(screen.getByText('Sağa kaydır: Doğru →')).toBeInTheDocument()
    expect(screen.getByText('← Sola kaydır: Yanlış')).toBeInTheDocument()
  })

  it('arka yüzden tekrar tıklayınca ön yüze döner (serbest çevirme)', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    expect(screen.getByText('Cevap 1')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Cevap 1'))

    expect(screen.queryByText('Cevap 1')).not.toBeInTheDocument()
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()
  })

  it('sağa sürükleme (yatay swipe) good rating gönderir ve sonraki karta geçer', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    const group = getCardGroup()
    fireEvent(group, pointer('pointerdown', 300, 200))
    fireEvent(group, pointer('pointermove', 420, 203))
    fireEvent(group, pointer('pointerup', 420, 203))

    await vi.advanceTimersByTimeAsync(200)
    expect(submitReview).toHaveBeenCalledWith(1, 0, 'good')
    expect(screen.getByText('Soru 2?')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('sola sürükleme again rating gönderir ve sonraki karta geçer', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    const group = getCardGroup()
    fireEvent(group, pointer('pointerdown', 400, 300))
    fireEvent(group, pointer('pointermove', 290, 297))
    fireEvent(group, pointer('pointerup', 290, 297))

    await vi.advanceTimersByTimeAsync(200)
    expect(submitReview).toHaveBeenCalledWith(1, 0, 'again')
    expect(screen.getByText('Soru 2?')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('yön eşiğini geçmeyen YAVAŞ sürükleme cevap sayılmaz', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    // performance da sahte: flick eşiği (hız) gerçek zaman yerine sanal zamandan ölçülür.
    vi.useFakeTimers({ toFake: ['performance', 'setTimeout', 'clearTimeout', 'Date'] })
    const group = getCardGroup()
    fireEvent(group, pointer('pointerdown', 300, 300))
    vi.advanceTimersByTime(200)
    fireEvent(group, pointer('pointermove', 340, 300))
    vi.advanceTimersByTime(200)
    fireEvent(group, pointer('pointerup', 340, 300))

    await vi.advanceTimersByTimeAsync(400)
    expect(submitReview).not.toHaveBeenCalled()
    expect(screen.getByText('Cevap 1')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('dikey sürükleme kartı oynatmaz (yatay baskınlık)', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    const group = getCardGroup()
    fireEvent(group, pointer('pointerdown', 300, 200))
    fireEvent(group, pointer('pointermove', 303, 360))
    expect(group.style.transform).toBe('rotateY(180deg)')

    fireEvent(group, pointer('pointerup', 303, 360))
    await vi.advanceTimersByTimeAsync(400)
    expect(submitReview).not.toHaveBeenCalled()
    expect(screen.getByText('Cevap 1')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('klavye → good rating gönderir ve sonraki karta geçer', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    fireEvent.keyDown(getCardGroup(), { key: 'ArrowRight' })

    await vi.advanceTimersByTimeAsync(200)
    expect(submitReview).toHaveBeenCalledWith(1, 0, 'good')
    expect(screen.getByText('Soru 2?')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('klavye ← again rating gönderir ve sonraki karta geçer', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    fireEvent.keyDown(getCardGroup(), { key: 'ArrowLeft' })

    await vi.advanceTimersByTimeAsync(200)
    expect(submitReview).toHaveBeenCalledWith(1, 0, 'again')
    expect(screen.getByText('Soru 2?')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('son kartta özet ekranı gösterir', async () => {
    const single = [dueCards[0]]
    render(<FlashcardPlayer dueCards={single} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Soru 1?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    vi.useFakeTimers()
    fireEvent.keyDown(getCardGroup(), { key: 'ArrowRight' })

    await vi.advanceTimersByTimeAsync(400)
    expect(screen.getByText(/Bugünlük tekrar tamamlandı/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kapat' })).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('boş due kuyruğunda bilgi mesajı gösterir', () => {
    render(<FlashcardPlayer dueCards={[]} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Tekrar bekleyen kart yok.')).toBeInTheDocument()
  })
})
