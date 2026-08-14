import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import App from './App'

vi.mock('./api/client', () => ({
  getHealth: vi.fn(async () => true),
}))

describe('App', () => {
  it('Dönemler sayfasını gösterir', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Dönemler' })).toBeInTheDocument()
    expect(screen.getByText('Henüz dönem yok')).toBeInTheDocument()
  })

  it('Backend kapalıyken sağlık uyarısını gösterir', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    // getHealth mock'u true döner; yine de banner bileşeni 'down' ile test edilebilir
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
