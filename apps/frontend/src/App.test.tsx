import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { getHealthInfo } from './api/client'

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
  getWeeklyStudy: vi.fn(async () => ({
    days: Array.from({ length: 7 }, (_, index) => ({
      date: `2026-09-0${index + 1}`,
      duration_sec: 600,
    })),
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
  it('Ana sayfayı karşılama paneliyle gösterir', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Çalışmaya başlamak için iyi bir an.' })).toBeInTheDocument()
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

    await screen.findAllByRole('heading', { name: 'Çalışmaya başlamak için iyi bir an.' })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('Backend kapalıyken uygulama çökmez ve yerel modda açılır', async () => {
    // authStore yeniden tasarlandı: `failed` bayrağı yok. getHealthInfo patlarsa
    // init bunu yakalar, yerel moda düşer ve normal kabuk açılır (hata ekranı yok).
    vi.mocked(getHealthInfo).mockRejectedValueOnce(new Error('backend kapalı'))

    // Bu dosyada RTL otomatik cleanup'ı yok (vitest `globals` kapalı): sorgular
    // bilinçli olarak kendi render kabına kapsanır (aşağıdaki `within`).
    const view = render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )
    const scoped = within(view.container)

    // 1) Hata ekranı YOK.
    expect(await scoped.findByRole('heading', { name: 'Çalışmaya başlamak için iyi bir an.' })).toBeInTheDocument()
    expect(scoped.queryByRole('button', { name: 'Tekrar dene' })).not.toBeInTheDocument()
  })
})
