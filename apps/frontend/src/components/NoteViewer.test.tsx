import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SavedNote } from '../api/notes'
import { NoteViewer } from './NoteViewer'

afterEach(() => {
  cleanup()
})

const note: SavedNote = {
  id: 1,
  chapter_id: 1,
  content_md:
    '### Konu A\n\nBağlı listeler doğrusaldır [1].\n\n- Düğümler işaretçi taşır [1].',
  citations_json: {
    topics: [
      {
        topic: 'Konu A',
        citations: [
          {
            id: 1,
            source_type: 'textbook',
            source_id: 9,
            page: 1,
            slide: null,
            chunk_id: 'chk_1_1_1',
            quote: 'Bağlı listeler doğrusaldır',
          },
        ],
      },
    ],
  },
  topics_json: [],
  generated_at: '2026-08-14',
  model_used: 'gemini-2.5-flash',
}

describe('NoteViewer', () => {
  it('markdown başlık ve gövdeyi gösterir; kalıntı atıf işaretleri TEMİZLENİR', () => {
    const { container } = render(<NoteViewer note={note} />)
    expect(screen.getByRole('heading', { name: 'Konu A' })).toBeInTheDocument()
    const matches = screen.getAllByText(
      (_, element) => element?.textContent?.includes('Bağlı listeler doğrusaldır') ?? false,
    )
    expect(matches.length).toBeGreaterThan(0)
    // Atıf sistemi kaldırıldı: [n] çipi buton olarak render EDİLMEZ, metinden silinir.
    expect(container.textContent).not.toContain('[1]')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('ham JSON zarfı kaydedilmiş notu markdown olarak render eder', () => {
    const brokenNote: SavedNote = {
      ...note,
      content_md:
        '### Konu A\n\n```json\n{"content": "### Konu A\\n\\nBağlı listeler doğrusaldır [1]."}\n```',
    }
    const { container } = render(<NoteViewer note={brokenNote} />)

    expect(container.textContent).not.toContain('"content"')
    expect(container.textContent).not.toContain('\\n')
    expect(container.querySelector('code')).toBeNull()
    expect(screen.getAllByRole('heading', { name: 'Konu A' }).length).toBeGreaterThan(0)
  })

  it('eski kayıtlardan gelen Kaynakça bölümü kullanıcıya GÖSTERİLMEZ', () => {
    const bibNote: SavedNote = {
      ...note,
      content_md:
        '### Konu A\n\nBağlı listeler doğrusaldır [1].\n\n## Kaynakça\n\n' +
        '- [1] Veri Yapıları.pdf, s. 42\n',
    }
    render(<NoteViewer note={bibNote} />)

    expect(screen.queryByRole('heading', { name: 'Kaynakça' })).not.toBeInTheDocument()
    expect(screen.queryByText('Veri Yapıları.pdf')).not.toBeInTheDocument()
  })
})
