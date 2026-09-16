import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EssayGraderForm } from './EssayGraderForm'

vi.mock('../api/essays', () => ({
  gradeEssay: vi.fn(async () => ({
    score: 85,
    criteria: [{ name: 'İçerik', score: 42, max: 50, comment: 'Konuya hâkim.' }],
    strengths: ['Güçlü giriş'],
    weaknesses: ['Zayıf sonuç'],
    quotes: [{ text: 'Örnek alıntı', comment: 'İyi örnek' }],
    confidence: 0.9,
  })),
  listEssays: vi.fn(async () => []),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('EssayGraderForm', () => {
  it('değerlendirme gönderilince skoru ve geri bildirimi render eder', async () => {
    render(<EssayGraderForm courseId={1} />)

    fireEvent.change(screen.getByLabelText('Ödev talimatı'), {
      target: { value: 'Bir kompozisyon yaz.' },
    })
    fireEvent.change(screen.getByLabelText('Ödev metni'), {
      target: { value: 'Kompozisyon metnim…' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Değerlendir' }))

    expect(await screen.findByText('85')).toBeInTheDocument()
    expect(screen.getByText('İçerik')).toBeInTheDocument()
    expect(screen.getByText('42 / 50')).toBeInTheDocument()
    expect(screen.getByText('Güçlü giriş')).toBeInTheDocument()
    expect(screen.getByText('Zayıf sonuç')).toBeInTheDocument()
    expect(screen.getByText(/Örnek alıntı/)).toBeInTheDocument()
  })
})
