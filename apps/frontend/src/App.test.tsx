import { fireEvent, render, screen, within } from '@testing-library/react'
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
    // BYOK kaldırıldı: sağlayıcı anahtarı girişleri son kullanıcıya gösterilmez.
    expect(screen.queryByText(/sağlayıcı zinciri/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/API anahtarı/)).not.toBeInTheDocument()
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

  /** Sidebar hover davranışı: masaüstünde kabuk "itme" durumuna geçer (içerik
   * sidebar'ın yanına kayar), MOBİLDE hover açmaz — sidebar off-canvas kalır.
   * Kapı `window.matchMedia('(min-width: 768px)')`; testlerde polyfill eşleşmez
   * (mobil) olduğundan masaüstü dalı kendi mock'uyla kurulur. */
  it('Sidebar hover\'ı yalnızca masaüstünde itme durumuna geçirir', async () => {
    const medya = (eslesir: boolean) => ({
      matches: eslesir,
      media: '',
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList

    const masaustu = render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )
    await within(masaustu.container).findByRole('heading', { name: 'Çalışmaya başlamak için iyi bir an.' })
    const kabukMasaustu = masaustu.container.querySelector('.stuhub-app')
    const yanMasaustu = masaustu.container.querySelector('.app-sidebar')
    expect(kabukMasaustu).not.toBeNull()
    expect(yanMasaustu).not.toBeNull()
    expect(kabukMasaustu?.className).not.toContain('stuhub-app--sidebar-open')

    vi.stubGlobal('matchMedia', vi.fn(() => medya(true)))
    fireEvent.mouseEnter(yanMasaustu as Element)
    expect(kabukMasaustu?.className).toContain('stuhub-app--sidebar-open')
    fireEvent.mouseLeave(yanMasaustu as Element)
    expect(kabukMasaustu?.className).not.toContain('stuhub-app--sidebar-open')

    // Mobil (polyfill varsayılanı: eşleşmez) → hover itme durumuna GEÇİRMEZ.
    vi.stubGlobal('matchMedia', vi.fn(() => medya(false)))
    const mobil = render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )
    await within(mobil.container).findByRole('heading', { name: 'Çalışmaya başlamak için iyi bir an.' })
    const kabukMobil = mobil.container.querySelector('.stuhub-app')
    const yanMobil = mobil.container.querySelector('.app-sidebar')
    fireEvent.mouseEnter(yanMobil as Element)
    expect(kabukMobil?.className).not.toContain('stuhub-app--sidebar-open')
    vi.unstubAllGlobals()
  })
})
