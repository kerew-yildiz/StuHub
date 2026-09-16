import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NextActionCard } from './NextActionCard'

const { fetchNextAction } = vi.hoisted(() => ({ fetchNextAction: vi.fn() }))

vi.mock('../api/nextAction', () => ({ fetchNextAction }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('NextActionCard', () => {
  it('action=cards → butona basınca target_id ile onOpenCards çağrılır', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'cards',
      reason: 'Vadesi geçmiş tekrar kartların var.',
      target_id: 42,
    })
    const onOpenCards = vi.fn()

    render(<NextActionCard courseId={3} onOpenCards={onOpenCards} />)

    expect(await screen.findByText('Vadesi geçmiş tekrar kartların var.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Kartları tekrarla' }))
    expect(onOpenCards).toHaveBeenCalledWith(42)
  })

  it('action=error_quiz → target_id olmadan onOpenErrorQuiz çağrılır', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'error_quiz',
      reason: "'Bağlı Liste' konusunda tekrarlayan hataların var.",
      target_id: null,
    })
    const onOpenErrorQuiz = vi.fn()

    render(<NextActionCard courseId={3} onOpenErrorQuiz={onOpenErrorQuiz} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Kurtarma turu başlat' }))
    expect(onOpenErrorQuiz).toHaveBeenCalledOnce()
  })

  it('action=none → buton gösterilmez', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'none',
      reason: 'Şu an için bekleyen bir öncelik yok.',
      target_id: null,
    })

    render(<NextActionCard courseId={3} />)

    expect(await screen.findByText('Şu an için bekleyen bir öncelik yok.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('istek başarısız olursa hata mesajı gösterir', async () => {
    fetchNextAction.mockRejectedValue(new Error('boom'))

    render(<NextActionCard courseId={3} />)

    expect(await screen.findByText('Öneri alınamadı. Lütfen tekrar deneyin.')).toBeInTheDocument()
  })
})
