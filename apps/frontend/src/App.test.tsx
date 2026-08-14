import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import App from './App'

vi.mock('./api/client', () => ({
  getHealth: vi.fn(async () => true),
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

vi.mock('./api/settings', () => ({
  settingsApi: {
    list: vi.fn(async () => ({ model: 'deepseek-chat' })),
    set: vi.fn(async () => ({ ok: true })),
  },
}))

describe('App', () => {
  it('Dönemler sayfasını boş durumla gösterir', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Dönemler' })).toBeInTheDocument()
    expect(await screen.findByText('Henüz dönem yok')).toBeInTheDocument()
  })

  it('Ayarlar sayfasını gösterir', async () => {
    render(
      <MemoryRouter initialEntries={['/ayarlar']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Ayarlar' })).toBeInTheDocument()
    expect(screen.getByLabelText('DeepSeek API anahtarı')).toBeInTheDocument()
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
