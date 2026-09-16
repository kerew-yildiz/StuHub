/**
 * Sidebar erişilebilirlik regresyonu: daraltılmış (varsayılan desktop) sidebar'da
 * tema `.nav-item__label`'ı display:none yapar (styles/theme.css:316), ikonlar da
 * aria-hidden olduğu için gezinme linkleri ekran okuyucuya İSİMSİZ görünüyordu.
 * Test, üretim koşulunu (aynı CSS kuralı) uygulayıp her linkin erişilebilir adını ölçer.
 */
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Sidebar } from './Sidebar'

vi.mock('../api/terms', () => ({
  termsApi: {
    list: vi.fn(async () => [
      { id: 3, name: '2026 Güz', start_date: null, end_date: null, created_at: '2026-01-01T00:00:00Z' },
    ]),
  },
}))

vi.mock('../api/courses', () => ({
  coursesApi: { listByTerm: vi.fn(async () => []) },
}))

vi.mock('../api/chapters', () => ({
  chaptersApi: { listByCourse: vi.fn(async () => []) },
}))

const LAYERS: Array<{ route: string; labels: string[] }> = [
  {
    route: '/',
    labels: ['Ana Sayfa', 'Dönemler', 'Takvim', 'Sınav Planı', 'Bugün Ne Çalışsam?', 'Ayarlar'],
  },
  {
    route: '/donemler/3',
    labels: ['2026 Güz', 'Dersler', 'Takvim', 'Sınav Planı', 'Bugün Ne Çalışsam?', 'Ayarlar'],
  },
  {
    route: '/dersler/7?view=notes',
    labels: [
      'Genel', 'Notlar', 'Kaydedilenler', 'Flashcard Practice', 'Kaydırarak Quiz',
      'Materyale Sor', 'Ödev Değerlendir', 'Ödev Taslak Koçu', 'Ayarlar',
    ],
  },
]

afterEach(cleanup)

function renderSidebar(route: string, open: boolean) {
  const style = document.createElement('style')
  style.textContent = '.nav-item--collapsed .nav-item__label{display:none;}'
  document.head.append(style)
  render(
    <MemoryRouter initialEntries={[route]}>
      <Sidebar open={open} onHoverOpen={() => undefined} onCloseMobile={() => undefined} />
    </MemoryRouter>,
  )
  return style
}

/** DOM'daki her link dolu erişilebilir ad taşır; beklenen hedefler adıyla bulunur. */
async function expectAllLinksNamed(labels: string[]) {
  const assertAllNamed = () => {
    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAccessibleName()
      expect(link).toHaveAccessibleName(link.querySelector('.nav-item__label')?.textContent ?? '')
    }
  }

  assertAllNamed()
  // Dönem katmanı async yüklenir — beklenen hedefler adlarıyla sorgulanabilmeli.
  for (const label of labels) {
    await screen.findByRole('link', { name: label })
  }
  assertAllNamed()
}

describe('Sidebar gezinme linklerinin erişilebilir adı', () => {
  it('daraltılmış sidebar\'da da üç katmanda ad taşır', async () => {
    for (const { route, labels } of LAYERS) {
      const style = renderSidebar(route, false)
      const label = document.querySelector('.nav-item--collapsed .nav-item__label') as HTMLElement | null
      // Ölçümün gerçekten kollabe durumu temsil ettiğini doğrula (kural etkisizse test boşa geçerdi).
      expect(label).not.toBeNull()
      expect(getComputedStyle(label as HTMLElement).display).toBe('none')
      await expectAllLinksNamed(labels)
      cleanup()
      style.remove()
    }
  })

  it('açık sidebar\'da adlar görünen etiketle aynıdır (Label in Name)', async () => {
    for (const { route, labels } of LAYERS) {
      const style = renderSidebar(route, true)
      await expectAllLinksNamed(labels)
      cleanup()
      style.remove()
    }
  })
})
