import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotebookPage } from '../pages/NotebookPage'
import { slidesApi } from '../api/slides'

// Gorunum bilesenlerinin (ChatPanel, ErrorLogPanel, ChapterQuizPanel) ag cagrilari:
// bos govde doner — test yalnizca hangi gorunumun bagli oldugunu olcer.
vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {},
  BASE_URL: '/api',
  setAccessToken: vi.fn(),
  authFetch: vi.fn(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })),
  apiFetch: vi.fn(async () => []),
}))

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
  listChapterNotes: vi.fn(async () => []),
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

vi.mock('../api/courses', () => ({
  coursesApi: {
    get: vi.fn(async () => ({ id: 1, name: 'Biyoloji', term_id: 1 })),
  },
}))

vi.mock('../api/terms', () => ({
  termsApi: {
    get: vi.fn(async () => ({ id: 1, name: '2026 Güz' })),
  },
}))

vi.mock('../api/topicProgress', () => ({
  getTopicProgress: vi.fn(async () => null),
}))

afterEach(() => {
  cleanup()
})

describe('NotebookPage sekmeleri', () => {
  it('çalışma alanlarını ?view= parametresiyle değiştirir (sidebar-driven workspace)', async () => {
    render(
      <MemoryRouter initialEntries={['/dersler/1/defter/1?view=notes']}>
        <Routes>
          <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
        </Routes>
      </MemoryRouter>,
    )

    // Notlar workspace'i — Guide Slides bölümü görünür
    expect(await screen.findByText('Guide Slides')).toBeInTheDocument()
    cleanup()

    render(
      <MemoryRouter initialEntries={['/dersler/1/defter/1?view=flashcards']}>
        <Routes>
          <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
        </Routes>
      </MemoryRouter>,
    )

    // Kartlar workspace'i — başlık görünür
    expect(await screen.findByRole('heading', { name: 'Kartlar' })).toBeInTheDocument()
    expect(screen.queryByText('Guide Slides')).not.toBeInTheDocument()
  })

  it('slaytlar varken "Yeni sunum ekle" görünür ve tıklanınca form açılır', async () => {
    vi.mocked(slidesApi.listByChapter).mockResolvedValueOnce([
      { id: 1, chapter_id: 1, material_id: null, slide_no: 1, content_text: 'İlk slayt' },
    ])
    render(
      <MemoryRouter initialEntries={['/dersler/1/defter/1?view=notes']}>
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

describe('NotebookPage sekme izolasyonu', () => {
  /** Gercek kullanimdaki sidebar gezinmesini taklit eden kap: gorunum degisimi
   * yalnizca URL (`view`) uzerinden yapilir. */
  function DefterRota() {
    return (
      <>
        <nav aria-label="test-gorunumler">
          <Link to="/dersler/1/defter/1">genel</Link>
          {['notes', 'flashcards', 'quiz', 'material-ask', 'mistakes', 'bilinmeyen-view'].map((view) => (
            <Link key={view} to={`/dersler/1/defter/1?view=${view}`}>
              {view}
            </Link>
          ))}
        </nav>
        <NotebookPage />
      </>
    )
  }

  const cizKayitli = (rota: string) =>
    render(
      <MemoryRouter initialEntries={[rota]}>
        <Routes>
          <Route path="/dersler/:courseId/defter/:chapterId" element={<DefterRota />} />
        </Routes>
      </MemoryRouter>,
    )

  const tekKok = async (beklenen: string) => {
    await waitFor(() => expect(document.querySelectorAll('[data-view-root]')).toHaveLength(1))
    expect(document.querySelector('[data-view-root]')).toHaveAttribute('data-view-root', beklenen)
  }

  it('Quiz -> Materyale Sor gecisinde eski quiz paneli ekranda kalmaz', async () => {
    cizKayitli('/dersler/1/defter/1?view=quiz')
    expect(await screen.findByText('QUIZLER')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'material-ask' }))

    await tekKok('ask')
    expect(screen.queryByText('QUIZLER')).toBeNull()
    expect(await screen.findByText('MATERYALE SOR')).toBeInTheDocument()
  })

  it('Notlar -> Hatalarim gecisinde not icerigi ekranda kalmaz', async () => {
    cizKayitli('/dersler/1/defter/1?view=notes')
    expect(await screen.findByText('Guide Slides')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('link', { name: 'mistakes' }))

    await tekKok('mistakes')
    expect(screen.queryByText('Guide Slides')).toBeNull()
    expect(await screen.findByText('HATALARIM')).toBeInTheDocument()
  })

  it('hizli ard arda gecis sonrasi tek gorunum kalir', async () => {
    cizKayitli('/dersler/1/defter/1?view=notes')

    fireEvent.click(screen.getByRole('link', { name: 'quiz' }))
    fireEvent.click(screen.getByRole('link', { name: 'material-ask' }))
    fireEvent.click(screen.getByRole('link', { name: 'mistakes' }))
    fireEvent.click(screen.getByRole('link', { name: 'flashcards' }))

    await tekKok('cards')
    expect(screen.queryByText('MATERYALE SOR')).toBeNull()
    expect(screen.queryByText('HATALARIM')).toBeNull()
  })

  it('taninmayan view degeri genel gorunume duser', async () => {
    cizKayitli('/dersler/1/defter/1?view=bilinmeyen-view')

    await tekKok('overview')
    expect(await screen.findByText('CHAPTER ÖZETİ')).toBeInTheDocument()
  })
})

describe('Konular boş durumu', () => {
  it('mesajı tam metin gösterir ve "Not üret" düğmesini ayrı flex alanında tutar', async () => {
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

    // Mesaj kesilmeden tek parça okunur (eski yerleşimde düğme metnin üstüne biniyordu)
    const message = await screen.findByText('Bu chapter için henüz konu özeti oluşmadı.')
    expect(message.textContent).toBe('Bu chapter için henüz konu özeti oluşmadı.')

    const row = message.closest('.empty-state') as HTMLElement | null
    expect(row).not.toBeNull()

    // Düğme mesajın içine gömülü değil; ayrı eleman olarak aynı boş-durum satırında durur
    const button = within(row as HTMLElement).getByRole('button', { name: 'Not üret' })
    expect(message.contains(button)).toBe(false)
    expect(button.contains(message)).toBe(false)
    expect(button).toBeEnabled()

    // Yerleşim sözleşmesi (jsdom layout ölçmez): satır flex + gap; mesaj kısalır, düğme küçülmez
    expect(String((row as HTMLElement).className)).toContain('flex')
    expect(String((row as HTMLElement).className)).toContain('items-center')
    expect(String((row as HTMLElement).className)).toContain('gap-3')
    expect(String(message.className)).toContain('min-w-0')
    expect(String(message.className)).not.toContain('truncate')
    expect(String(button.className)).toContain('shrink-0')
  })
})
