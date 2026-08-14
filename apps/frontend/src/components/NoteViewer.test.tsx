import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { resolveCitation, type SavedNote } from '../api/notes'
import { NoteViewer } from './NoteViewer'

afterEach(() => {
  cleanup()
})

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

  it('web atıfında fetch çağrılmaz; başlık ve URL gösterilir', async () => {
    vi.mocked(resolveCitation).mockClear()
    const webNote: SavedNote = {
      id: 2,
      chapter_id: 1,
      content_md: '### Konu A\n\nBu bilgi [1] kaynağından gelir.\n',
      citations_json: {
        topics: [
          {
            topic: 'Konu A',
            citations: [
              {
                id: 1,
                source_type: 'web',
                source_id: null,
                page: null,
                slide: null,
                chunk_id: 'web-1',
                quote: 'Doğrudan alıntı metni',
                title: 'Örnek Kaynak',
                url: 'https://example.com/makale',
              },
            ],
          },
        ],
      },
      topics_json: [],
      generated_at: '2026-08-14',
      model_used: 'deepseek-chat',
    }

    render(<NoteViewer note={webNote} />)
    fireEvent.click(screen.getByRole('button', { name: '[1]' }))

    // Başlık + alıntı + tıklanabilir URL gösterilir
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(await screen.findByText('Örnek Kaynak')).toBeInTheDocument()
    expect(screen.getByText('“Doğrudan alıntı metni”')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'https://example.com/makale' })
    expect(link).toHaveAttribute('href', 'https://example.com/makale')
    expect(link).toHaveAttribute('target', '_blank')

    // Web atıfı için kaynak parça API'sine gidilmez
    expect(vi.mocked(resolveCitation)).not.toHaveBeenCalled()
  })
})
