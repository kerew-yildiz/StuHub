import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { TermsPage } from './TermsPage'

vi.mock('../api/terms', () => ({
  termsApi: {
    list: vi.fn(async () => [
      {
        id: 1,
        name: '2026 Bahar',
        start_date: '2026-02-01',
        end_date: '2026-06-01',
        created_at: '2026-01-01T00:00:00Z',
      },
    ]),
    create: vi.fn(async () => ({})),
    update: vi.fn(async () => ({})),
    remove: vi.fn(async () => undefined),
  },
}))

vi.mock('../api/settings', () => ({
  settingsApi: {
    list: vi.fn(async () => ({ model: 'deepseek-chat', onboarding_done: '1' })),
    set: vi.fn(async () => ({ ok: true })),
  },
}))

vi.mock('../api/streaks', () => ({
  getStreakSummary: vi.fn(async () => ({
    streak_days: 3,
    today_counts: { note: 0, quiz: 2, flashcard: 5, chat: 1 },
    daily_goal: 3,
    progress_percent: 66,
  })),
}))

describe('TermsPage düzenleme', () => {
  it('Düzenle butonu render edilir ve tıklanınca mini form açılır', async () => {
    render(
      <MemoryRouter>
        <TermsPage />
      </MemoryRouter>,
    )

    const editButton = await screen.findByRole('button', {
      name: '2026 Bahar dönemini düzenle',
    })
    expect(editButton).toBeInTheDocument()

    fireEvent.click(editButton)
    expect(screen.getByLabelText('Dönem adı')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kaydet' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'İptal' })).toBeInTheDocument()
  })
})
