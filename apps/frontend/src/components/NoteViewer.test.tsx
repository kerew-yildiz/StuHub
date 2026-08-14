import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { SavedNote } from '../api/notes'
import { NoteViewer } from './NoteViewer'

vi.mock('../api/notes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/notes')>()
  return {
    ...actual,
    resolveCitation: vi.fn(async () => ({
      chunk_id: 'chk_1_1_1',
      course_id: 1,
      material_id: 9,
      text: 'Kaynak parça metni.',
      page: 1,
      slide: null,
    })),
  }
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
  model_used: 'deepseek-chat',
}

describe('NoteViewer', () => {
  it('markdown ve atıf düğmesini gösterir', () => {
    render(<NoteViewer note={note} />)
    expect(screen.getByRole('heading', { name: 'Konu A' })).toBeInTheDocument()
    // metin, inline atıf düğmesi nedeniyle bölünmüş olabilir — textContent ile denetle
    const matches = screen.getAllByText(
      (_, element) => element?.textContent?.includes('Bağlı listeler doğrusaldır') ?? false,
    )
    expect(matches.length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: '[1]' }).length).toBeGreaterThan(0)
  })

  it('atıf tıklanınca pop-up açılır ve Esc ile kapanır', async () => {
    render(<NoteViewer note={note} />)
    const buttons = screen.getAllByRole('button', { name: '[1]' })
    expect(buttons.length).toBeGreaterThan(0)
    fireEvent.click(buttons[0])
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(await screen.findByText('Kaynak parça metni.')).toBeInTheDocument()

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
