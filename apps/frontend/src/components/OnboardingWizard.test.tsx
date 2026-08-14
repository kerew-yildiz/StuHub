import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { coursesApi } from '../api/courses'
import { settingsApi } from '../api/settings'
import { termsApi } from '../api/terms'
import { OnboardingWizard } from './OnboardingWizard'

vi.mock('../api/terms', () => ({
  termsApi: {
    list: vi.fn(async () => []),
    create: vi.fn(async () => ({
      id: 1,
      name: '2026 Bahar',
      start_date: null,
      end_date: null,
      created_at: '2026-01-01T00:00:00Z',
    })),
  },
}))

vi.mock('../api/courses', () => ({
  coursesApi: {
    create: vi.fn(async () => ({
      id: 1,
      term_id: 1,
      name: '',
      instructor: null,
      metadata_json: {},
      created_at: '2026-01-01T00:00:00Z',
    })),
  },
}))

vi.mock('../api/settings', () => ({
  settingsApi: {
    list: vi.fn(async () => ({})),
    set: vi.fn(async () => ({ ok: true })),
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('OnboardingWizard', () => {
  it('adım adım ilerler ve dönem + dersleri oluşturur', async () => {
    const onComplete = vi.fn()
    render(<OnboardingWizard onComplete={onComplete} />)

    // Adım 1 — boş ad ilerlemez
    fireEvent.click(screen.getByRole('button', { name: 'İleri' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Dönem adı boş olamaz.')

    fireEvent.change(screen.getByLabelText('Dönem adı'), { target: { value: '2026 Bahar' } })
    fireEvent.click(screen.getByRole('button', { name: 'İleri' }))
    expect(screen.getByText('Bu dönem hangi dersleri alıyorsun?')).toBeInTheDocument()

    // Adım 2 — virgülle ayrılmış dersler
    fireEvent.change(screen.getByLabelText('Dersler (virgülle ayır)'), {
      target: { value: 'Veri Yapıları, Analiz II' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'İleri' }))
    expect(screen.getByText('Özet — onaylayıp başla.')).toBeInTheDocument()

    // Adım 3 — başlat
    fireEvent.click(screen.getByRole('button', { name: 'Başlat' }))

    await waitFor(() => expect(termsApi.create).toHaveBeenCalledWith({ name: '2026 Bahar' }))
    expect(coursesApi.create).toHaveBeenCalledTimes(2)
    expect(coursesApi.create).toHaveBeenCalledWith(1, { name: 'Veri Yapıları', instructor: null })
    expect(coursesApi.create).toHaveBeenCalledWith(1, { name: 'Analiz II', instructor: null })
    expect(settingsApi.set).toHaveBeenCalledWith('onboarding_done', '1')
    expect(onComplete).toHaveBeenCalled()
  })

  it('Atla bayrağı yazar ve kapatır', async () => {
    const onComplete = vi.fn()
    render(<OnboardingWizard onComplete={onComplete} />)

    fireEvent.click(screen.getByRole('button', { name: 'Atla' }))

    await waitFor(() =>
      expect(settingsApi.set).toHaveBeenCalledWith('onboarding_done', '1'),
    )
    expect(termsApi.create).not.toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalled()
  })
})
