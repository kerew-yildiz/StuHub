import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TourOverlay } from './TourOverlay'
import { TOUR_STEPS } from './steps'
import { startHelpTour, stopHelpTour } from './tourStore'
import { useTourController } from './useTourController'

/**
 * Adım geçişi tutarlılığı (BULGU-66/67): popover her adımda AYNI konum geçişiyle
 * taşınmalı; reduced-motion'da geçiş olmamalı ama konum yine de değişmeli.
 * Kapanış sözleşmesi de burada: Kapat ve son adımın aksiyonu turu kapatır,
 * rota adımı kullanıcıyı gerçek sayfaya taşır.
 *
 * jsdom'da düzen (layout) ve CSS transition motoru yok — bu yüzden ölçüt:
 * (a) her adımda konum değişir, (b) geçiş bildirimi tüm adımlarda tek ve aynı,
 * (c) reduced-motion'da bildirim yok. Canlı kanıt (gerçek Chromium,
 * `document.getAnimations()`): apps/frontend/scripts/tur-gecis-olcum.mjs.
 */

// jsdom düzen hesaplamaz: anchor kutuları elle verilir (/takvim geometrisine yakın).
// Verilmezse tüm adımlar (0,0) döner ve konum değişimi ölçülemez.
const KUTULAR: Record<string, { x: number; y: number; w: number; h: number }> = {
  'global-search': { x: 8, y: 8, w: 56, h: 40 },
  'help-button': { x: 1752, y: 15, w: 40, h: 40 },
  'notification-button': { x: 1804, y: 15, w: 40, h: 40 },
  'browser-fullscreen-button': { x: 1856, y: 15, w: 40, h: 40 },
  'profile-trigger': { x: 8, y: 1028, w: 56, h: 40 },
}

// jsdom rAF'i gerçek zamanlı çalıştırır; kare adımları elle sürülür (konum
// geçişinin açıldığı kare deterministik olsun diye).
const kareKuyrugu: FrameRequestCallback[] = []
const kare = (t = 16) => {
  for (const cb of kareKuyrugu.splice(0)) cb(t)
}

const sahneKur = () => {
  document.body.innerHTML = ''
  // Anchor'sız adımlar (rota adımları) için DOM elemanı üretilmez.
  for (const s of TOUR_STEPS.global) {
    const anchor = s.anchor
    if (!anchor) continue
    const k = KUTULAR[anchor]
    if (!k) continue
    const el = document.createElement('button')
    el.setAttribute('data-tour-id', anchor)
    el.getBoundingClientRect = () =>
      ({
        x: k.x,
        y: k.y,
        width: k.w,
        height: k.h,
        left: k.x,
        top: k.y,
        right: k.x + k.w,
        bottom: k.y + k.h,
        toJSON: () => '',
      }) as DOMRect
    document.body.appendChild(el)
  }
}

const hareketKur = (azHareket: boolean) =>
  vi.stubGlobal('matchMedia', (sorgu: string) => ({
    matches: azHareket,
    media: sorgu,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))

/** Popover düğümü: testlerin tamamı aynı seçiciyi kullanır (test seam'i). */
const popover = () => screen.getByRole('dialog') as HTMLElement
const ileriye = { name: 'İleri' }

/** Rota adımı sözleşmesi için konum gözlemcisi (tur overlay'i router ister). */
function Konum() {
  const { pathname } = useLocation()
  return <span data-testid="konum">{pathname}</span>
}

const renderTur = (onClose: () => void = () => {}) =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <Konum />
      <TourOverlay layer="global" open onClose={onClose} />
    </MemoryRouter>,
  )

beforeEach(() => {
  kareKuyrugu.length = 0
  // Ölçüm koşumuyla aynı viewport: jsdom varsayılanı 1024x768'de sağ üst
  // anchor'lar taşma kuralına takılıp aynı konuma düşerdi.
  Object.defineProperty(window, 'innerWidth', { value: 1920, configurable: true })
  Object.defineProperty(window, 'innerHeight', { value: 1080, configurable: true })
  // jsdom scrollIntoView tanımlamaz; bileşen anchor'ı görünüme kaydırır.
  Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, writable: true, value: vi.fn() })
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => kareKuyrugu.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {})
})

afterEach(() => {
  cleanup()
  Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('TourOverlay adım geçişi', () => {
  it('konum her adımda değişir ve geçiş tüm adımlarda aynıdır (4/4 tutarlı)', () => {
    sahneKur()
    hareketKur(false)
    renderTur()

    // İlk yerleşim (açılış) animasyonsuz: popover viewport ortasından anchor'a süzülmez.
    expect(popover().style.transition).toBe('')
    act(() => kare())

    const konumlar = [popover().style.transform]
    const gecisler = [popover().style.transition]
    for (let i = 0; i < 4; i += 1) {
      fireEvent.click(screen.getByRole('button', ileriye))
      konumlar.push(popover().style.transform)
      gecisler.push(popover().style.transition)
    }

    // 5 adım → 5 farklı konum: her adım geçişinde popover taşınır.
    expect(new Set(konumlar).size).toBe(5)
    // Tek geçiş bildirimi: bazı adımlar animasyonlu bazıları değil durumu yok.
    expect(new Set(gecisler).size).toBe(1)
    expect(gecisler[0]).toContain('transform')
    expect(gecisler[0]).toContain('var(--duration-state)')
  })

  it('reduced-motion: geçiş yok, konum yine değişir', () => {
    sahneKur()
    hareketKur(true)
    renderTur()
    act(() => kare())

    const onceki = popover().style.transform
    fireEvent.click(screen.getByRole('button', ileriye))

    expect(popover().style.transform).not.toBe(onceki)
    expect(popover().style.transition).toBe('')
  })

  it('Kapat butonu turu kapatır', () => {
    sahneKur()
    hareketKur(false)
    const kapatan = vi.fn()
    renderTur(kapatan)

    fireEvent.click(screen.getByRole('button', { name: 'Kapat' }))

    expect(kapatan).toHaveBeenCalledTimes(1)
  })

  it('rota adımı kullanıcıyı gerçek sayfaya taşır ve "Turu bitir" turu kapatır', () => {
    sahneKur()
    hareketKur(false)
    const kapatan = vi.fn()
    renderTur(kapatan)

    for (let i = 0; i < 5; i += 1) fireEvent.click(screen.getByRole('button', ileriye))

    // 6. adım rota adımı: spotlight yok ama anlatı ve rota gezinmesi var.
    expect(screen.getByText('Sıra dönemlerinde')).toBeTruthy()
    expect(screen.getByTestId('konum').textContent).toBe('/donemler')

    fireEvent.click(screen.getByRole('button', { name: 'Turu bitir' }))
    expect(kapatan).toHaveBeenCalledTimes(1)
  })
})

/** Controller'ı dışa açık API üzerinden süren sahne (startHelpTour sözleşmesi). */
function Kontrolcu() {
  return useTourController().overlay
}

describe('startHelpTour sözleşmesi', () => {
  afterEach(() => stopHelpTour())

  it('turu başlatır, açıkken tekrar çağrılırsa 1. adımdan başlatır', () => {
    sahneKur()
    hareketKur(false)
    render(
      <MemoryRouter initialEntries={['/']}>
        <Kontrolcu />
      </MemoryRouter>,
    )

    act(() => startHelpTour())
    expect(screen.getByText('Sidebar ve arama')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', ileriye))
    expect(screen.getByText('Yardım ve tur')).toBeTruthy()

    // Tur açıkken yeniden başlatma senaryosu: tekrar çağırmak baştan başlatır.
    act(() => startHelpTour())
    expect(screen.getByText('Sidebar ve arama')).toBeTruthy()

    act(() => stopHelpTour())
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
