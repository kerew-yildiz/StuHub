import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ComparisonTable } from './ComparisonTable'

const { getGlossary, getComparison, generateComparison } = vi.hoisted(() => ({
  getGlossary: vi.fn(),
  getComparison: vi.fn(),
  generateComparison: vi.fn(),
}))

vi.mock('../api/guides', () => ({ getGlossary, getComparison, generateComparison }))

const COMPARISON = {
  id: 5,
  kind: 'comparison' as const,
  created_at: '2026-01-01T00:00:00Z',
  content_json: {
    concepts: ['Yığın', 'Kuyruk'],
    pairs: [
      {
        a: 'Yığın',
        b: 'Kuyruk',
        similarities: ['İkisi de doğrusal veri yapısıdır.'],
        differences: [
          { aspect: 'erişim düzeni', a: 'LIFO', b: 'FIFO' },
          { aspect: 'tipik kullanım', a: 'geri alma', b: 'iş sırası' },
        ],
        confusion: 'Ekleme ve çıkarma uçları karıştırılır.',
      },
    ],
  },
}

function glossaryTerms(terms: string[]) {
  return terms.map((term) => ({
    term,
    definition: '',
    chapter_id: null,
    chapter_title: null,
    note_id: null,
    position: null,
    heading: null,
  }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ComparisonTable', () => {
  it('iki kavram seçilince karşılaştırmayı üretir ve tabloyu render eder', async () => {
    getGlossary.mockResolvedValue(glossaryTerms(['Yığın', 'Kuyruk', 'Ağaç']))
    getComparison.mockResolvedValueOnce(null).mockResolvedValueOnce(COMPARISON)
    generateComparison.mockResolvedValue({
      id: 5,
      course_id: 1,
      chapter_id: null,
      kind: 'comparison',
    })

    render(<ComparisonTable courseId={1} />)

    const yigin = await screen.findByRole('button', { name: 'Yığın' })
    // Tek seçimle üretim kapalı.
    fireEvent.click(yigin)
    expect(screen.getByRole('button', { name: 'Karşılaştır' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Kuyruk' }))
    fireEvent.click(screen.getByRole('button', { name: 'Karşılaştır' }))

    expect(await screen.findByText('LIFO')).toBeInTheDocument()
    expect(generateComparison).toHaveBeenCalledWith(1, ['Yığın', 'Kuyruk'])
    expect(screen.getByText('FIFO')).toBeInTheDocument()
    expect(screen.getByText('İkisi de doğrusal veri yapısıdır.')).toBeInTheDocument()
    expect(screen.getByText('Ekleme ve çıkarma uçları karıştırılır.')).toBeInTheDocument()
  })

  it('altıdan fazla kavram seçtirmez', async () => {
    getGlossary.mockResolvedValue(glossaryTerms(['a', 'b', 'c', 'd', 'e', 'f', 'g']))
    getComparison.mockResolvedValue(null)

    render(<ComparisonTable courseId={1} />)

    await screen.findByRole('button', { name: 'a' })
    for (const name of ['a', 'b', 'c', 'd', 'e', 'f']) {
      fireEvent.click(screen.getByRole('button', { name }))
    }
    expect(screen.getByRole('button', { name: 'g' })).toBeDisabled()
    expect(screen.getByText('En az 2, en fazla 6 kavram seç (6 seçili).')).toBeInTheDocument()
  })

  it('anahtar terim yoksa önce özet üretme yönergesini gösterir', async () => {
    getGlossary.mockResolvedValue([])
    getComparison.mockResolvedValue(null)

    render(<ComparisonTable courseId={1} />)

    expect(await screen.findByText(/Önce bölüm özetleri üret/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Karşılaştır' })).toBeNull()
  })

  it('üretim hatasında backend mesajını gösterir', async () => {
    getGlossary.mockResolvedValue(glossaryTerms(['Yığın', 'Kuyruk']))
    getComparison.mockResolvedValue(null)
    generateComparison.mockRejectedValue(new Error('Önce özet üret.'))

    render(<ComparisonTable courseId={1} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Yığın' }))
    fireEvent.click(screen.getByRole('button', { name: 'Kuyruk' }))
    fireEvent.click(screen.getByRole('button', { name: 'Karşılaştır' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Önce özet üret.')
  })
})
