import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { unsaveQuestion } from '../api/feed'
import { listSavedQuestions, type SavedQuestion } from '../api/saved'
import { SavedQuestionsPage } from './SavedQuestionsPage'

vi.mock('../api/saved', () => ({
  listSavedQuestions: vi.fn(),
}))
vi.mock('../api/feed', () => ({
  unsaveQuestion: vi.fn(),
}))

const mockList = vi.mocked(listSavedQuestions)
const mockUnsave = vi.mocked(unsaveQuestion)

afterEach(() => {
  cleanup()
  mockList.mockReset()
  mockUnsave.mockReset()
})

function saved(overrides: Partial<SavedQuestion> = {}): SavedQuestion {
  return {
    feed_id: 1,
    question: "Newton'in ikinci yasası nedir?",
    options: ['F=ma', 'E=mc²', 'PV=nRT', 'F=kx'],
    correct_index: 0,
    explanation: 'Kuvvet, kütle ile ivmenin çarpımına eşittir.',
    topic: 'Mekanik',
    chapter_id: 4,
    chapter_title: 'Newton Yasaları',
    course_id: 2,
    course_name: 'Fizik I',
    saved_at: '2026-09-08T10:00:00Z',
    ...overrides,
  }
}

describe('SavedQuestionsPage', () => {
  it('kaydedilen soruları ders/chapter bilgisiyle listeler, doğru şıkkı vurgular', async () => {
    mockList.mockResolvedValueOnce([saved()])

    render(<SavedQuestionsPage />)

    expect(await screen.findByText(/ikinci yasası/)).toBeInTheDocument()
    expect(screen.getByText('Fizik I · Newton Yasaları')).toBeInTheDocument()
    expect(screen.getByText('Mekanik')).toBeInTheDocument()
    expect(screen.getByText('F=ma')).toHaveClass('text-stuhub-success')
    expect(screen.getByText('Kuvvet, kütle ile ivmenin çarpımına eşittir.')).toBeInTheDocument()
  })

  it('boş durumda bilgilendirme gösterir', async () => {
    mockList.mockResolvedValueOnce([])

    render(<SavedQuestionsPage />)

    expect(await screen.findByText(/Henüz kaydedilmiş soru yok/)).toBeInTheDocument()
  })

  it('kayıt kaldırma optimistik çalışır, sunucuya bildirir', async () => {
    mockList.mockResolvedValueOnce([saved()])
    mockUnsave.mockResolvedValueOnce(undefined)

    render(<SavedQuestionsPage />)
    await screen.findByText(/ikinci yasası/)

    fireEvent.click(screen.getByRole('button', { name: 'Kaydı kaldır' }))

    expect(screen.queryByText(/ikinci yasası/)).not.toBeInTheDocument()
    await waitFor(() => expect(mockUnsave).toHaveBeenCalledWith(1))
  })

  it('sunucu hatasında kayıt geri eklenir ve hata mesajı gösterilir', async () => {
    mockList.mockResolvedValueOnce([saved()])
    mockUnsave.mockRejectedValueOnce(new Error('offline'))

    render(<SavedQuestionsPage />)
    await screen.findByText(/ikinci yasası/)

    fireEvent.click(screen.getByRole('button', { name: 'Kaydı kaldır' }))
    expect(screen.queryByText(/ikinci yasası/)).not.toBeInTheDocument()

    expect(await screen.findByText(/Kayıt kaldırılamadı/)).toBeInTheDocument()
    expect(await screen.findByText(/ikinci yasası/)).toBeInTheDocument()
  })
})
