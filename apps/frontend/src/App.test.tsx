import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

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
})
