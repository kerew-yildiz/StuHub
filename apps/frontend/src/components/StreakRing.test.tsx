import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StreakRing } from './StreakRing'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function stubStreakSummary(body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
}

describe('StreakRing', () => {
  it('yüzde, streak ve günlük etkinlik metnini gösterir', async () => {
    stubStreakSummary({
      streak_days: 3,
      today_counts: { note: 0, quiz: 2, flashcard: 5, chat: 1 },
      daily_goal: 3,
      progress_percent: 66,
    })
    render(<StreakRing />)

    expect(await screen.findByText('🔥 3 gün streak')).toBeInTheDocument()
    expect(screen.getByText('Bugün 8/3 etkinlik')).toBeInTheDocument()
    expect(screen.getByText('66%')).toBeInTheDocument()
  })

  it('bugün etkinlik yoksa boş durum mikro-metnini gösterir', async () => {
    stubStreakSummary({
      streak_days: 0,
      today_counts: { note: 0, quiz: 0, flashcard: 0, chat: 0 },
      daily_goal: 3,
      progress_percent: 0,
    })
    render(<StreakRing />)

    expect(await screen.findByText('🔥 0 gün streak')).toBeInTheDocument()
    expect(
      screen.getByText('Bugün ilk etkinliğini yap — not üret, quiz çöz ya da kart tekrarla.'),
    ).toBeInTheDocument()
  })
})
