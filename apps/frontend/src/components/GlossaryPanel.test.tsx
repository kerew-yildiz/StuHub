import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { GlossaryPanel } from './GlossaryPanel'

const { getGlossary } = vi.hoisted(() => ({ getGlossary: vi.fn() }))

vi.mock('../api/guides', () => ({ getGlossary }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('GlossaryPanel', () => {
  it('terimleri baş harflerine göre gruplar ve ilk geçtiği nota bağlar', async () => {
    getGlossary.mockResolvedValue([
      {
        term: 'Ağaç',
        definition: 'Kök altında toplanan düğümler.',
        chapter_id: 2,
        chapter_title: 'Ağaçlar',
        note_id: 7,
        position: 12,
        heading: 'Hiyerarşik yapılar',
      },
      {
        term: 'Kuyruk',
        definition: '',
        chapter_id: null,
        chapter_title: null,
        note_id: null,
        position: null,
        heading: null,
      },
    ])

    render(
      <MemoryRouter>
        <GlossaryPanel courseId={3} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Ağaç')).toBeInTheDocument()
    expect(getGlossary).toHaveBeenCalledWith(3)
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('K')).toBeInTheDocument()
    expect(screen.getByText('Kök altında toplanan düğümler.')).toBeInTheDocument()
    expect(screen.getByText('“Hiyerarşik yapılar” başlığı altında', { exact: false })).toBeInTheDocument()

    // Notta geçmeyen terimin bağlantısı üretilmez (kırık link yok).
    const links = screen.getAllByRole('link', { name: 'Nota git' })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/dersler/3/defter/2')
    expect(screen.getByText('Bu terim notlarında henüz açıklanmamış.')).toBeInTheDocument()
  })

  it('sözlük boşsa özet üretme yönergesini gösterir', async () => {
    getGlossary.mockResolvedValue([])

    render(
      <MemoryRouter>
        <GlossaryPanel courseId={1} />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/Sözlük henüz boş/)).toBeInTheDocument()
  })
})
