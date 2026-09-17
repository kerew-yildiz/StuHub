import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NextActionCard } from './NextActionCard'
import { useHelpTourOpen } from '../tour'

const { fetchNextAction, listErrors } = vi.hoisted(() => ({
  fetchNextAction: vi.fn(),
  listErrors: vi.fn(),
}))

vi.mock('../api/nextAction', () => ({ fetchNextAction }))
vi.mock('../api/errors', () => ({ listErrors }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Gerçek tur store'unu okur — kartın UI turu başlatmadığının ölçüsü (regresyon). */
function TurDurumu() {
  return <span data-testid="tur">{String(useHelpTourOpen())}</span>
}

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

  it('action=read_chapter → butona basınca target_id ile onOpenChapter çağrılır', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'read_chapter',
      reason: 'Henüz hiç çalışmadığın bir bölüm var.',
      target_id: 7,
    })
    const onOpenChapter = vi.fn()

    render(<NextActionCard courseId={3} onOpenChapter={onOpenChapter} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Bölümü oku' }))
    expect(onOpenChapter).toHaveBeenCalledWith(7)
  })

  it('action=error_quiz → hatanın yaşandığı bölümü açar, UI turu başlatmaz', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'error_quiz',
      reason: "'Bağlı Liste' konusunda tekrarlayan hataların var.",
      target_id: null,
    })
    listErrors.mockResolvedValue([
      {
        question_text: 'Soru',
        given_answer: 'A',
        correct_answer: 'B',
        topic: 'Bağlı Liste',
        quiz_id: 5,
        chapter_id: 9,
        created_at: '2026-09-08T08:30:28+00:00',
        repeat_count: 3,
      },
    ])
    const onOpenChapter = vi.fn()

    render(
      <>
        <NextActionCard courseId={3} onOpenChapter={onOpenChapter} />
        <TurDurumu />
      </>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Kurtarma turu başlat' }))

    await waitFor(() => expect(onOpenChapter).toHaveBeenCalledWith(9))
    expect(listErrors).toHaveBeenCalledWith(3, { onlyRepeated: true })
    expect(screen.getByTestId('tur')).toHaveTextContent('false')
  })

  it('action=error_quiz + hatanın bölümü yok → boş mesaj gösterir, yönlendirmez', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'error_quiz',
      reason: "'Genel' konusunda tekrarlayan hataların var.",
      target_id: null,
    })
    listErrors.mockResolvedValue([])
    const onOpenChapter = vi.fn()

    render(<NextActionCard courseId={3} onOpenChapter={onOpenChapter} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Kurtarma turu başlat' }))

    expect(await screen.findByText(/bağlı bir bölüm yok/i)).toBeInTheDocument()
    expect(onOpenChapter).not.toHaveBeenCalled()
  })

  it('action=error_quiz + hata günlüğü okunamazsa → mesaj gösterir, yönlendirmez', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'error_quiz',
      reason: "'Bağlı Liste' konusunda tekrarlayan hataların var.",
      target_id: null,
    })
    listErrors.mockRejectedValue(new Error('boom'))
    const onOpenChapter = vi.fn()

    render(<NextActionCard courseId={3} onOpenChapter={onOpenChapter} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Kurtarma turu başlat' }))

    expect(await screen.findByText(/başlatılamadı/i)).toBeInTheDocument()
    expect(onOpenChapter).not.toHaveBeenCalled()
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

  it('hedefi olmayan (target_id=null) aksiyonda buton gösterilmez', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'read_chapter',
      reason: 'Henüz hiç çalışmadığın bir bölüm var.',
      target_id: null,
    })

    render(<NextActionCard courseId={3} onOpenChapter={vi.fn()} />)

    expect(await screen.findByText('Henüz hiç çalışmadığın bir bölüm var.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('hedef açıcı bağlanmamışsa buton gösterilmez (sessiz tıklama olmaz)', async () => {
    fetchNextAction.mockResolvedValue({
      action: 'cards',
      reason: 'Vadesi geçmiş tekrar kartların var.',
      target_id: 42,
    })

    render(<NextActionCard courseId={3} />)

    expect(await screen.findByText('Vadesi geçmiş tekrar kartların var.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('istek başarısız olursa hata mesajı gösterir', async () => {
    fetchNextAction.mockRejectedValue(new Error('boom'))

    render(<NextActionCard courseId={3} />)

    expect(await screen.findByText('Öneri alınamadı. Lütfen tekrar deneyin.')).toBeInTheDocument()
  })
})
