import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotebookPage } from '../pages/NotebookPage'

vi.mock('../api/chapters', () => ({
  chaptersApi: {
    get: vi.fn(async () => ({
      id: 1,
      course_id: 1,
      title: 'Hücre Biyolojisi',
      created_at: '2026-01-01T00:00:00Z',
    })),
    listByCourse: vi.fn(async () => []),
  },
}))

vi.mock('../api/slides', () => ({
  slidesApi: {
    listByChapter: vi.fn(async () => []),
    upload: vi.fn(),
    remove: vi.fn(),
  },
}))

vi.mock('../api/notes', () => ({
  getNote: vi.fn(async () => null),
  exportNotePdf: vi.fn(),
}))

vi.mock('../api/quizzes', () => ({
  listQuizzes: vi.fn(async () => []),
  removeQuiz: vi.fn(),
}))

vi.mock('../api/flashcards', () => ({
  listFlashcardSets: vi.fn(async () => []),
  deleteFlashcardSet: vi.fn(),
}))

vi.mock('../api/materials', () => ({
  materialsApi: {
    get: vi.fn(),
    listByCourse: vi.fn(async () => []),
  },
}))

afterEach(() => {
  cleanup()
})

describe('NotebookPage sekmeleri', () => {
  it('çalışma modu sekmelerini render eder ve geçişi günceller', async () => {
    render(
      <MemoryRouter initialEntries={['/dersler/1/defter/1']}>
        <Routes>
          <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
        </Routes>
      </MemoryRouter>,
    )

    const notlar = await screen.findByRole('tab', { name: 'Notlar' })
    const kartlar = screen.getByRole('tab', { name: 'Kartlar' })
    const quiz = screen.getByRole('tab', { name: 'Quiz' })

    expect(notlar).toHaveAttribute('aria-selected', 'true')
    expect(kartlar).toHaveAttribute('aria-selected', 'false')
    expect(quiz).toHaveAttribute('aria-selected', 'false')

    fireEvent.click(kartlar)
    expect(kartlar).toHaveAttribute('aria-selected', 'true')
    expect(notlar).toHaveAttribute('aria-selected', 'false')

    fireEvent.click(quiz)
    expect(quiz).toHaveAttribute('aria-selected', 'true')
    expect(kartlar).toHaveAttribute('aria-selected', 'false')
  })
})
