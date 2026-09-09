import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotebookPage } from '../pages/NotebookPage'
import { slidesApi } from '../api/slides'

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
    const quiz = screen.getByRole('tab', { name: 'Kaydırarak Quiz' })

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

  it('slaytlar varken "Yeni sunum ekle" görünür ve tıklanınca form açılır', async () => {
    vi.mocked(slidesApi.listByChapter).mockResolvedValueOnce([
      { id: 1, chapter_id: 1, material_id: null, slide_no: 1, content_text: 'İlk slayt' },
    ])
    render(
      <MemoryRouter initialEntries={['/dersler/1/defter/1']}>
        <Routes>
          <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
        </Routes>
      </MemoryRouter>,
    )

    // Liste dolu olduğu için form kapalı başlar ve ekleme düğmesi görünür
    const addButton = await screen.findByRole('button', { name: 'Yeni sunum ekle +' })
    expect(addButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByLabelText('Sunum dosyası (PDF / PPTX)')).not.toBeInTheDocument()

    fireEvent.click(addButton)
    expect(screen.getByLabelText('Sunum dosyası (PDF / PPTX)')).toBeInTheDocument()
  })
})
