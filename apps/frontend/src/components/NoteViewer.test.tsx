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
  model_used: 'gemini-2.5-flash',
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
    // materyal atıfı köşeli kalır: dış-bağlantı oku TAŞIMAZ (web atıfından farkı)
    expect(screen.getAllByRole('button', { name: '[1]' })[0].textContent).not.toContain('↗')
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
      content_md: '### Konu A\n\nBu bilgi ⟨1⟩ kaynağından gelir.\n',
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
      model_used: 'gemini-2.5-flash',
    }

    render(<NoteViewer note={webNote} />)
    const webChip = screen.getByRole('button', { name: '⟨1⟩' })
    // web atıfı açılı parantezli + dış-bağlantı oklu (renk farkı YOK, biçim farkı)
    expect(webChip.textContent).toContain('↗')
    fireEvent.click(webChip)

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

  it('kaynakça: web satırındaki URL bağlantı, materyal satırı düz metin', () => {
    const bibNote: SavedNote = {
      ...note,
      content_md:
        '### Konu A\n\nBağlı listeler doğrusaldır [1].\n\n## Kaynakça\n\n' +
        '- [1] Veri Yapıları.pdf, s. 42\n- ⟨2⟩ Web Kaynağı — <https://example.com/makale>\n',
    }
    render(<NoteViewer note={bibNote} />)

    expect(screen.getByRole('heading', { name: 'Kaynakça' })).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'https://example.com/makale' })
    expect(link).toHaveAttribute('href', 'https://example.com/makale')
    expect(link).toHaveAttribute('target', '_blank')
    // Kaynakça bölümü kendi atıf listesini taşımaz: numaralar bağlantıya dönüşmez.
    expect(screen.queryByRole('link', { name: '[1]' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '⟨2⟩' })).not.toBeInTheDocument()
  })
})
