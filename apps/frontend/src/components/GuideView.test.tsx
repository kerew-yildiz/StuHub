import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ConceptMapGuide, SummaryGuide } from '../api/guides'
import { GuideView } from './GuideView'

afterEach(() => {
  cleanup()
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
    expect(container.querySelectorAll('[data-cm-node]')).toHaveLength(3)
    expect(screen.getByText('Mitoz')).toBeInTheDocument()
    expect(screen.getByText('Mayoz')).toBeInTheDocument()
    // Mermaid gerçekten çizilir (mock'lanmaz) — jsdom'da bu ~12 sn sürüyor ve
    // vitest'in 5 sn'lik varsayılanını aşıyordu. Yavaşlık render'ın kendisinde,
    // testin mantığında değil; bu yüzden mock'lamak yerine süre tanınır.
  }, 30_000)
})
