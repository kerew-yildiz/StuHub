import { act, fireEvent, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createGlobalStudySession, sendStudyTimeHeartbeat } from '../api/studySessions'
import { useStudyTimeTracker } from './useStudyTimeTracker'

vi.mock('../api/studySessions', () => ({
  createGlobalStudySession: vi.fn().mockResolvedValue(undefined),
  createStudySession: vi.fn().mockResolvedValue(undefined),
  sendStudyTimeHeartbeat: vi.fn().mockResolvedValue(undefined),
}))

function Takip() {
  useStudyTimeTracker()
  return null
}

function ac(yol: string) {
  return render(
    <MemoryRouter initialEntries={[yol]}>
      <Takip />
    </MemoryRouter>,
  )
}

async function ilerle(saniye: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(saniye * 1000)
  })
}

function gorunurluk(deger: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { value: deger, configurable: true })
}

describe('useStudyTimeTracker', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    gorunurluk('visible')
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('chapter görünümünde her 45 sn için bir heartbeat gönderir', async () => {
    const { unmount } = ac('/dersler/4/defter/7')

    await ilerle(45)

    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(1)
    expect(sendStudyTimeHeartbeat).toHaveBeenCalledWith(4, 7, expect.any(String), 45)

    await ilerle(45)

    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(2)
    const kimlikler = vi.mocked(sendStudyTimeHeartbeat).mock.calls.map((c) => c[2])
    // Her aralık kendi kimliğiyle gider — backend aynı kimliği tekrar görürse çift saymaz.
    expect(kimlikler[0]).not.toBe(kimlikler[1])
    unmount()
  })

  it('chapter dışı sayfada global blok yazar, chapter heartbeat göndermez', async () => {
    const { unmount } = ac('/dersler/4')

    // 90 sn'lik etkileşim penceresi dolmasın diye etkileşim tazelenir.
    for (let tur = 0; tur < 10; tur += 1) {
      fireEvent.keyDown(document)
      await ilerle(30)
    }

    expect(sendStudyTimeHeartbeat).not.toHaveBeenCalled()
    expect(createGlobalStudySession).toHaveBeenCalledTimes(1)
    expect(createGlobalStudySession).toHaveBeenCalledWith(expect.any(String), 300)
    unmount()
  })

  it('sekme gizliyken süre saymaz, görünür olunca devam eder', async () => {
    const { unmount } = ac('/dersler/4/defter/7')

    gorunurluk('hidden')
    await ilerle(90)
    expect(sendStudyTimeHeartbeat).not.toHaveBeenCalled()

    gorunurluk('visible')
    fireEvent(document, new Event('visibilitychange'))
    await ilerle(45)
    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('etkileşim 90 sn kesilince sayacı durdurur', async () => {
    const { unmount } = ac('/dersler/4/defter/7')

    await ilerle(45)
    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(1)

    await ilerle(300)
    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(2)

    fireEvent.keyDown(document)
    await ilerle(45)
    expect(sendStudyTimeHeartbeat).toHaveBeenCalledTimes(3)
    unmount()
  })
})
