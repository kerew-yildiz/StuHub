import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { getHealthInfo } from './api/client'
import { useAuthStore } from './stores/authStore'

import App from './App'

vi.mock('./api/client', () => ({
  getHealth: vi.fn(async () => true),
  getHealthInfo: vi.fn(async () => ({
    status: 'ok',
    app: 'stuhub',
    version: '0.1.0',
    saas_mode: false,
  })),
  setAccessToken: vi.fn(),
  apiFetch: vi.fn(),
}))

vi.mock('./api/terms', () => ({
  termsApi: {
    list: vi.fn(async () => []),
    create: vi.fn(async () => ({})),
    update: vi.fn(async () => ({})),
    remove: vi.fn(async () => undefined),
  },
}))

vi.mock('./api/streaks', () => ({
  getStreakSummary: vi.fn(async () => ({
    streak_days: 3,
    today_counts: { note: 0, quiz: 2, flashcard: 5, chat: 1 },
    daily_goal: 3,
    progress_percent: 66,
  })),
}))

vi.mock('./api/settings', () => ({
  settingsApi: {
    list: vi.fn(async () => ({ onboarding_done: '1' })),
    set: vi.fn(async () => ({ ok: true })),
    llmStatus: vi.fn(async () => []),
  },
}))

describe('App', () => {
  it('Dönemler sayfasını boş durumla gösterir', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Dönemler' })).toBeInTheDocument()
    expect(await screen.findByText('Henüz dönem yok')).toBeInTheDocument()
  })

  it('Ayarlar sayfasını gösterir', async () => {
    render(
      <MemoryRouter initialEntries={['/ayarlar']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Ayarlar' })).toBeInTheDocument()
    expect(screen.getByLabelText('1. Google Gemini API anahtarı')).toBeInTheDocument()
  })

  it('Backend ayaktayken sağlık uyarısı görünmez', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    await screen.findByText('Henüz dönem yok')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('Backend yanıt vermezse "Yükleniyor…"da kilitlenmez, tekrar dene ekranı gösterir', async () => {
    // `/health` hiç sonuçlanmayan bir promise döndüğünde (asılı backend) uygulama
    // eskiden sonsuza kadar "Yükleniyor…" gösteriyordu — kullanıcı hiçbir şey öğrenmiyordu.
    // Asla settle etmeyen promise: asılı backend'i taklit eder.
    vi.mocked(getHealthInfo).mockReturnValueOnce(Promise.withResolvers<never>().promise)
    vi.useFakeTimers({ shouldAdvanceTime: true })

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByText('Yükleniyor…')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(10_000)

    expect(
      await screen.findByText(/Sunucuya bağlanılamıyor/),
    ).toBeInTheDocument()

    // Tekrar dene sağlıklı yanıt alınca uygulama normal açılır.
    fireEvent.click(screen.getByRole('button', { name: 'Tekrar dene' }))
    expect(await screen.findByRole('heading', { name: 'Dönemler' })).toBeInTheDocument()
  })
})

afterEach(() => {
  // Vitest'te `globals` kapalı olduğu için otomatik cleanup çalışmıyor; render'lar
  // birikirse aynı metin birden çok kez bulunuyor.
  cleanup()
  vi.useRealTimers()
  useAuthStore.setState({ loading: true, failed: false, session: null, user: null, saasMode: false })
  vi.mocked(getHealthInfo).mockReset()
  vi.mocked(getHealthInfo).mockResolvedValue({
    status: 'ok',
    app: 'stuhub',
    version: '0.1.0',
    saas_mode: false,
  })
})
