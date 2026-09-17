import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { formatDateShort } from '../lib/format'
import { CourseNotesPanel } from './CourseNotesPanel'

const { listByCourse, listChapterNotes } = vi.hoisted(() => ({
  listByCourse: vi.fn(),
  listChapterNotes: vi.fn(),
}))

vi.mock('../api/chapters', () => ({ chaptersApi: { listByCourse } }))
vi.mock('../api/notes', () => ({ listChapterNotes }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function note(id: number, chapterId: number, generatedAt: string) {
  return {
    id,
    chapter_id: chapterId,
    content_md: `# Not ${id}`,
    citations_json: { topics: [] },
    topics_json: [],
    generated_at: generatedAt,
    model_used: null,
  }
}

function renderPanel(courseId = 1) {
  return render(
    <MemoryRouter>
      <CourseNotesPanel courseId={courseId} />
    </MemoryRouter>,
  )
}

describe('CourseNotesPanel', () => {
  it('chapterın tüm notlarını yeniden eskiye, tarih ve Aç bağlantısıyla listeler', async () => {
    listByCourse.mockResolvedValue([
      { id: 5, course_id: 1, title: 'Ağaçlar', created_at: '2026-01-01T00:00:00' },
    ])
    // Arşiv ucu sırasız dönse bile panel id DESC gösterir.
    listChapterNotes.mockResolvedValue([
      note(4, 5, '2026-01-05T09:00:00'),
      note(12, 5, '2026-03-12T09:00:00'),
      note(9, 5, '2026-02-02T09:00:00'),
    ])

    renderPanel()

    expect(await screen.findByText('Ağaçlar')).toBeInTheDocument()
    expect(listChapterNotes).toHaveBeenCalledWith(5)

    const rows = await screen.findAllByRole('link')
    expect(rows).toHaveLength(3)
    rows.forEach((row) => {
      expect(row).toHaveAttribute('href', '/dersler/1/defter/5?view=notes')
      expect(row.textContent).toContain('Not')
      expect(row.textContent).toContain('Aç')
    })

    // Yeni → eski sıra: en güncel not en üstte (id 12, 9, 4).
    const expectedDates = ['2026-03-12T09:00:00', '2026-02-02T09:00:00', '2026-01-05T09:00:00']
      .map((value) => formatDateShort(value))
    expect(rows.map((row) => expectedDates.findIndex((date) => row.textContent?.includes(date)))).toEqual([0, 1, 2])
  })

  it('notu olmayan chapterda mevcut boş durumu korur ve chapter başına tek istek atar', async () => {
    listByCourse.mockResolvedValue([
      { id: 5, course_id: 1, title: 'Ağaçlar', created_at: '2026-01-01T00:00:00' },
      { id: 6, course_id: 1, title: 'Grafolar', created_at: '2026-01-02T00:00:00' },
    ])
    listChapterNotes.mockImplementation(async (chapterId: number) =>
      chapterId === 5 ? [note(12, 5, '2026-03-12T09:00:00')] : [],
    )

    renderPanel()

    expect(await screen.findByText('Bu chapter için henüz not üretmedin.')).toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(1)
    expect(listChapterNotes).toHaveBeenCalledTimes(2)
  })
})
