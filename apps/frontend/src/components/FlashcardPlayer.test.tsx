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

describe('FlashcardPlayer', () => {
  it('ön yüzü gösterir ve tıklayınca arka yüzü çevirir', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    expect(screen.queryByText('Cevap 1')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))

    expect(screen.getByText('Cevap 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Again' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hard' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Good' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Easy' })).toBeInTheDocument()
  })

  it('Again doğru parametrelerle submitReview çağırır ve sonraki karta geçer', async () => {
    render(<FlashcardPlayer dueCards={dueCards} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Again' }))

    expect(await screen.findByText('Soru 2?')).toBeInTheDocument()
    expect(submitReview).toHaveBeenCalledWith(1, 0, 'again')
  })

  it('son kartta özet ekranı gösterir', async () => {
    const single = [dueCards[0]]
    render(<FlashcardPlayer dueCards={single} onFinished={vi.fn()} onExit={vi.fn()} />)
    await screen.findByText('Soru 1?')

    fireEvent.click(screen.getByRole('button', { name: /Soru 1/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Good' }))

    expect(await screen.findByText(/Bugünlük tekrar tamamlandı/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kapat' })).toBeInTheDocument()
  })

  it('boş due kuyruğunda bilgi mesajı gösterir', () => {
    render(<FlashcardPlayer dueCards={[]} onFinished={vi.fn()} onExit={vi.fn()} />)
    expect(screen.getByText('Tekrar bekleyen kart yok.')).toBeInTheDocument()
  })
})
