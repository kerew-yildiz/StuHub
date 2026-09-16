import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { submitReview, type DueCard } from '../api/flashcards'
import { FlashcardPlayer } from './FlashcardPlayer'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

vi.mock('../api/flashcards', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/flashcards')>()
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

describe('FlashcardPlayer', () => {
  it('ön yüzü gösterir ve tıklayınca arka yüzü çevirir', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    expect(screen.queryByText('Cevap 1')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))

    expect(screen.getByText('Cevap 1')).toBeInTheDocument()
    // §42 swipe modeli: yön ipuçları görünür, 4 buton grid'i YOK
    expect(screen.getByText('Sağa kaydır: Doğru →')).toBeInTheDocument()
    expect(screen.getByText('← Sola kaydır: Yanlış')).toBeInTheDocument()
  })

  it('sağa kaydırma (klavye →) good rating gönderir ve sonraki karta geçer', async () => {
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

  it('sola kaydırma (klavye ←) again rating gönderir ve sonraki karta geçer', async () => {
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
