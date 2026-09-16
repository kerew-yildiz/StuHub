import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConceptMapGuide, SummaryGuide } from '../api/guides'
import { GuideView } from './GuideView'

// Mermaid gerçekten çizilirse jsdom'da layout ölçümü (getBBox/getComputedTextLength)
// yüzünden ~12 sn sürüyor ve vitest'in 5 sn'lik varsayılanını aşıyordu — test iki
// koşuda bu yüzden düştü. İddia çizimin kendisi değil: üretilen flowchart tanımı TÜM
// düğümleri/kenarları içeriyor, bu tanım mermaid.render'a veriliyor ve dönen SVG
// işaretlenerek DOM'a giriyor. Mock, sahte SVG'yi render'a gelen tanımdan türetir —
// tanımda düğüm eksikse DOM'da da eksik olur, "tüm düğümler" kapsağı korunur.
const { renderMock } = vi.hoisted(() => ({
  renderMock: vi.fn<(id: string, definition: string) => Promise<{ svg: string }>>(),
}))

vi.mock('mermaid', () => ({
  default: { initialize: vi.fn(), render: renderMock },
}))

renderMock.mockImplementation(async (_id, definition) => ({
  // Her düğüm satırı (`  id["etiket"]:::sınıf`) için bir `.node` — MermaidDiagram'ın
  // `data-cm-node` işaretlemesi gerçek kod yolunda çalışmaya devam eder.
  svg: `<svg xmlns="http://www.w3.org/2000/svg">${definition
    .split('\n')
    .flatMap((line) => line.match(/\["(.+)"\]:::/)?.[1] ?? [])
    .map((label) => `<g class="node"><text>${label}</text></g>`)
    .join('')}</svg>`,
}))

afterEach(() => {
  cleanup()
  renderMock.mockClear()
})

describe('GuideView', () => {
  it('özet rehberini markdown, anahtar terim ve sınav odaklarıyla render eder', () => {
    const summary: SummaryGuide = {
      id: 1,
      kind: 'summary',
      created_at: '2026-01-01T00:00:00Z',
      content_json: {
        summary_md: '## Özet\nBu bir özettir.',
        key_terms: ['Mitoz'],
        exam_focus: ['Hücre bölünmesi'],
      },
    }

    render(<GuideView guide={summary} />)

    expect(screen.getByText('Bu bir özettir.')).toBeInTheDocument()
    expect(screen.getByText('Mitoz')).toBeInTheDocument()
    expect(screen.getByText('Sınav Odakları')).toBeInTheDocument()
    expect(screen.getByText('Hücre bölünmesi')).toBeInTheDocument()
  })

  it('kavram haritasında tüm düğümleri Mermaid SVG olarak çizer', async () => {
    const conceptMap: ConceptMapGuide = {
      id: 2,
      kind: 'concept_map',
      created_at: '2026-01-01T00:00:00Z',
      content_json: {
        nodes: [
          { id: 'a', label: 'Hücre', importance: 2 },
          { id: 'b', label: 'Mitoz', importance: 1 },
          { id: 'c', label: 'Mayoz', importance: 1 },
        ],
        edges: [
          { from: 'a', to: 'b', label: 'bölünür' },
          { from: 'a', to: 'c' },
        ],
      },
    }

    const { container } = render(<GuideView guide={conceptMap} />)

    await screen.findByText('Hücre')

    // Tanım tüm düğümleri ve kenarları taşır, mermaid'e tek seferde verilir.
    expect(renderMock).toHaveBeenCalledTimes(1)
    const [, definition] = renderMock.mock.calls[0]
    expect(definition).toContain('flowchart LR')
    for (const label of ['Hücre', 'Mitoz', 'Mayoz']) {
      expect(definition).toContain(`"${label}"]`)
    }
    expect(definition).toContain('a -->|bölünür| b')
    expect(definition).toContain('a --> c')

    // Dönen SVG DOM'a girer ve her düğüm işaretlenir.
    expect(container.querySelectorAll('[data-cm-node]')).toHaveLength(3)
    expect(screen.getByText('Mitoz')).toBeInTheDocument()
    expect(screen.getByText('Mayoz')).toBeInTheDocument()
    expect(screen.getByLabelText('Kavram haritası')).toBeInTheDocument()
  })
})
