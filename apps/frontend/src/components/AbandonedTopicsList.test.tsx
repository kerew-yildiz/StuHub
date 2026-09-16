import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AbandonedTopicsList } from './AbandonedTopicsList'

const { fetchAbandonedTopics, generateErrorQuiz } = vi.hoisted(() => ({
  fetchAbandonedTopics: vi.fn(),
  generateErrorQuiz: vi.fn(),
}))

vi.mock('../api/abandoned', () => ({ fetchAbandonedTopics }))
vi.mock('../api/errors', () => ({ generateErrorQuiz }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AbandonedTopicsList', () => {
  it('terk edilmiş konu yoksa boş durum mesajı gösterir', async () => {
    fetchAbandonedTopics.mockResolvedValue([])

    render(<AbandonedTopicsList courseId={3} />)

    expect(
      await screen.findByText('Terk edilmiş bir konun yok — tüm konularla temas halindesin.'),
    ).toBeInTheDocument()
  })

  it('"kurtarma turu başlat" tıklanınca o TEK konu için quiz üretir ve teslim eder', async () => {
    fetchAbandonedTopics.mockResolvedValue([
      { topic: 'Bağlı Liste', chapter_id: 5, last_activity: null },
    ])
    const quizResult = { course_id: 3, topics: ['Bağlı Liste'], questions: [] }
    generateErrorQuiz.mockResolvedValue(quizResult)
    const onStartRecovery = vi.fn()

    render(<AbandonedTopicsList courseId={3} onStartRecovery={onStartRecovery} />)

    expect(await screen.findByText('Bağlı Liste')).toBeInTheDocument()
    expect(screen.getByText('Hiç çalışılmadı')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Kurtarma turu başlat/ }))

    await screen.findByRole('button', { name: /Kurtarma turu başlat/ })
    expect(generateErrorQuiz).toHaveBeenCalledWith(3, ['Bağlı Liste'])
    expect(onStartRecovery).toHaveBeenCalledWith(quizResult, {
      topic: 'Bağlı Liste',
      chapter_id: 5,
      last_activity: null,
    })
  })

  it('konu listesi alınamazsa hata mesajı gösterir', async () => {
    fetchAbandonedTopics.mockRejectedValue(new Error('boom'))

    render(<AbandonedTopicsList courseId={3} />)

    expect(
      await screen.findByText('Terk edilmiş konular alınamadı. Lütfen tekrar deneyin.'),
    ).toBeInTheDocument()
  })
})
