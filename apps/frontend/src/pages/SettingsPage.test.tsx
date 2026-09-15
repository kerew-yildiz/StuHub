import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { settingsApi, type LLMProviderStatus } from '../api/settings'
import { SettingsPage } from './SettingsPage'

vi.mock('../api/settings', () => ({
  settingsApi: { list: vi.fn(), set: vi.fn(), llmStatus: vi.fn() },
}))

const mockList = vi.mocked(settingsApi.list)
const mockStatus = vi.mocked(settingsApi.llmStatus)

afterEach(() => {
  cleanup()
  mockList.mockReset()
  mockStatus.mockReset()
})

function status(overrides: Partial<LLMProviderStatus> = {}): LLMProviderStatus {
  return {
    name: 'gemini',
    label: 'Google Gemini 3.1 Flash Lite',
    configured: true,
    cooldown_until: null,
    active: false,
    ...overrides,
  }
}

describe('SettingsPage — sağlayıcı zinciri', () => {
  it('backend zincirindeki BEŞ sağlayıcıyı da gösterir', async () => {
    // 2026-09-10: `cerebras` alanı UI'da yoktu; yapılandırılmış ve kullanılabilir bir
    // sağlayıcı kullanıcıya hiç görünmüyordu (backend PROVIDER_CHAIN 5, UI 4).
    mockList.mockResolvedValueOnce({})
    mockStatus.mockResolvedValueOnce([])

    render(<SettingsPage />)

    expect(await screen.findByLabelText(/Google Gemini API anahtarı/)).toBeInTheDocument()
    expect(screen.getByLabelText(/OpenRouter API anahtarı/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Groq API anahtarı/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Cerebras API anahtarı/)).toBeInTheDocument()
    expect(screen.getByLabelText(/GitHub Token/)).toBeInTheDocument()
  })

  it('cooldown\'da olmayan yedek sağlayıcıya "Kota doldu" DEMEZ', async () => {
    // Zincirde yalnızca ilk uygun sağlayıcı `active` olur; arkadakiler kotası dolduğu
    // için değil, sırası gelmediği için bekler. Eski rozet ikisini karıştırıyordu.
    mockList.mockResolvedValueOnce({})
    mockStatus.mockResolvedValueOnce([
      status({ name: 'gemini', active: true }),
      status({ name: 'openrouter', active: false, cooldown_until: null }),
    ])

    render(<SettingsPage />)

    expect(await screen.findByText('Aktif')).toBeInTheDocument()
    expect(screen.getByText('Yedekte')).toBeInTheDocument()
    expect(screen.queryByText(/Kota doldu/)).not.toBeInTheDocument()
  })

  it('gerçekten cooldown\'daki sağlayıcıyı bitiş zamanıyla gösterir', async () => {
    mockList.mockResolvedValueOnce({})
    mockStatus.mockResolvedValueOnce([
      status({ name: 'gemini', active: true }),
      status({ name: 'groq', active: false, cooldown_until: '2026-09-11T00:00:00+00:00' }),
    ])

    render(<SettingsPage />)

    expect(await screen.findByText(/Kota doldu —/)).toBeInTheDocument()
  })

  it('yapılandırılmamış sağlayıcıya hiç rozet basmaz', async () => {
    mockList.mockResolvedValueOnce({})
    mockStatus.mockResolvedValueOnce([status({ name: 'groq', configured: false })])

    render(<SettingsPage />)

    await screen.findByLabelText(/Groq API anahtarı/)
    expect(screen.queryByText('Yedekte')).not.toBeInTheDocument()
    expect(screen.queryByText('Aktif')).not.toBeInTheDocument()
  })
})
