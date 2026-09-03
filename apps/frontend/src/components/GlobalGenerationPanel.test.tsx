import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useGenerationStore, type GenerationJob } from '../stores/generationStore'
import { GlobalGenerationPanel } from './GlobalGenerationPanel'

vi.mock('../lib/useAnimatedProgress', () => ({
  useAnimatedProgress: (target: number) => target,
}))

function runningJob(overrides: Partial<GenerationJob> = {}): GenerationJob {
  return {
    kind: 'note',
    targetId: 1,
    label: 'Not: Test',
    percent: 42,
    message: 'Hazırlanıyor…',
    status: 'running',
    error: null,
    liveContent: '',
    ...overrides,
  }
}

beforeEach(() => {
  useGenerationStore.setState({ jobs: [] })
})

afterEach(() => {
  cleanup()
  useGenerationStore.setState({ jobs: [] })
})

describe('GlobalGenerationPanel', () => {
  it('kapalı durumda kompakt çipi gösterir (aktif iş özeti)', () => {
    useGenerationStore.setState({ jobs: [runningJob()] })
    render(<GlobalGenerationPanel />)

    const chip = screen.getByRole('button', { name: 'Üretim durumunu aç' })
    expect(chip).toHaveAttribute('aria-expanded', 'false')
    expect(chip.textContent).toContain('Not: Test')
    expect(chip.textContent).toContain('%42')
    // Kapalıyken iş listesi içeriği görünmez
    expect(screen.queryByText('Üretim Durumu')).not.toBeInTheDocument()
  })

  it('tıklanınca iş listesi açılır, "Kapat ▾" ile kapanır', () => {
    useGenerationStore.setState({ jobs: [runningJob()] })
    render(<GlobalGenerationPanel />)

    fireEvent.click(screen.getByRole('button', { name: 'Üretim durumunu aç' }))
    expect(screen.getByText('Üretim Durumu')).toBeInTheDocument()
    expect(screen.getByText('Not: Test')).toBeInTheDocument()
    expect(screen.getByText('Hazırlanıyor…')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Kapat ▾' }))
    expect(screen.queryByText('Üretim Durumu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Üretim durumunu aç' })).toBeInTheDocument()
  })

  it('aktif iş yoksa ve hata varsa uyarı rozeti gösterir', () => {
    useGenerationStore.setState({
      jobs: [runningJob({ status: 'error', percent: 100, message: 'Hata' })],
    })
    render(<GlobalGenerationPanel />)

    const chip = screen.getByRole('button', { name: 'Üretim durumunu aç' })
    expect(chip.querySelector('svg')).toBeInTheDocument()
    expect(chip.textContent).toContain('Hata')
  })

  it('iş yokken hiçbir şey render etmez', () => {
    useGenerationStore.setState({ jobs: [] })
    const { container } = render(<GlobalGenerationPanel />)
    expect(container).toBeEmptyDOMElement()
  })
})
