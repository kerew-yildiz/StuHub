import { cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CursorRing } from './CursorRing'

// jsdom rAF'i gerçek zamanlı çalıştırır; kare adımlarını deterministik yapmak
// için kuyruk elle sürülür (test bu kuyruğu boşaltınca bileşen bir kare ilerler).
const kareKuyrugu: FrameRequestCallback[] = []
const kare = (t = 16) => {
  const kuyruk = kareKuyrugu.splice(0)
  for (const cb of kuyruk) cb(t)
}

type Ortam = { isaretci: 'fine' | 'coarse'; azHareket: boolean }

const ortamKur = ({ isaretci, azHareket }: Ortam) => {
  vi.stubGlobal('matchMedia', (sorgu: string) => ({
    matches: sorgu.includes('pointer: fine') ? isaretci === 'fine' : azHareket,
    media: sorgu,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

// jsdom PointerEvent'i tanimlamaz; bilesen yalnizca clientX/clientY/target okur,
// bu yuzden ayni olay TIPLERI MouseEvent ile gonderilir.
const pointerOlay = (tip: string, x = 0, y = 0) => new MouseEvent(tip, { bubbles: true, clientX: x, clientY: y })

const panelKur = () => {
  const panel = document.createElement('article')
  panel.className = 'glass-panel'
  panel.getBoundingClientRect = () => ({ left: 0, top: 0, right: 400, bottom: 200, width: 400, height: 200, x: 0, y: 0, toJSON: () => '' }) as DOMRect
  const buton = document.createElement('button')
  panel.appendChild(buton)
  const baslik = document.createElement('h2')
  baslik.textContent = 'Hucre Solunumu'
  panel.appendChild(baslik)
  const paragraf = document.createElement('p')
  paragraf.textContent = 'Hucre solunumu glikoliz ile baslar.'
  panel.appendChild(paragraf)
  const girdi = document.createElement('input')
  girdi.type = 'text'
  panel.appendChild(girdi)
  const alan = document.createElement('textarea')
  panel.appendChild(alan)
  const duzenlenebilir = document.createElement('div')
  duzenlenebilir.setAttribute('contenteditable', 'true')
  panel.appendChild(duzenlenebilir)
  const kutu = document.createElement('input')
  kutu.type = 'checkbox'
  panel.appendChild(kutu)
  document.body.appendChild(panel)
  const hareket = (hedef: Element, x: number, y: number) => hedef.dispatchEvent(pointerOlay('pointermove', x, y))
  return { panel, buton, baslik, paragraf, girdi, alan, duzenlenebilir, kutu, hareket }
}

const halka = () => document.querySelector('.cursor-ring')
const halkaSinif = () => String(halka()?.className)
const panelDegeri = (ad: string) => (document.querySelector('.glass-panel') as HTMLElement).style.getPropertyValue(ad)

beforeEach(() => {
  kareKuyrugu.length = 0
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => kareKuyrugu.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {})
  document.documentElement.className = ''
})

afterEach(() => {
  cleanup()
  Reflect.deleteProperty(document, 'caretRangeFromPoint')
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
  document.documentElement.removeAttribute('style')
})

describe('CursorRing', () => {
  it('pointer:coarse ortamda mount edilmez ve imlec kurallarini acmaz', () => {
    ortamKur({ isaretci: 'coarse', azHareket: false })
    render(<CursorRing />)

    expect(halka()).toBeNull()
    expect(document.documentElement.classList.contains('cursor-ring-on')).toBe(false)
  })

  it('pointer:fine ortamda ilk hareketle gorunur olur ve ters-paralaks leke konumunu panele yazar', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    document.documentElement.style.setProperty('--reflect-parallax', '-0.3')
    document.documentElement.style.setProperty('--reflect-lerp', '1')
    document.documentElement.style.setProperty('--reflect-edge-range', '120')
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 300, 160)
    kare()

    expect(halkaSinif()).toContain('cursor-ring--visible')
    expect(document.documentElement.classList.contains('cursor-ring-on')).toBe(true)
    expect((halka() as HTMLElement).style.transform).toBe('translate3d(300.00px, 160.00px, 0)')
    // panel merkezi (200,100): leke = merkez + (imlec - merkez) * -0.3
    expect(panelDegeri('--cursor-x')).toBe('170')
    expect(panelDegeri('--cursor-y')).toBe('82')
  })

  it('kenar isigi imlece yakin kenarda parlar, uzak kenarda soner', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    document.documentElement.style.setProperty('--reflect-parallax', '-0.3')
    document.documentElement.style.setProperty('--reflect-lerp', '1')
    document.documentElement.style.setProperty('--reflect-edge-range', '120')
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 300, 160)
    kare()

    expect(panelDegeri('--edge-b')).toBe('0.444') // 40px -> (1-40/120)^2
    expect(panelDegeri('--edge-r')).toBe('0.028') // 100px -> (1-100/120)^2
    expect(panelDegeri('--edge-l')).toBe('0.000') // 300px -> menzil disi
    expect(panelDegeri('--edge-t')).toBe('0.000')
  })

  it('etkilesimli elemanda hover sinifi alir, duz panelde almaz', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { panel, buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 40, 40)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--hover')

    hareket(panel, 60, 40)
    kare()
    expect(halkaSinif()).not.toContain('cursor-ring--hover')
  })

  it('yazma alanlari (input/textarea/contenteditable) metin durumuna girer; etkilesimli onceligi korunur', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { buton, girdi, alan, duzenlenebilir, kutu, hareket } = panelKur()
    render(<CursorRing />)

    // Etkilesimli onceligi: buton hover alir, I YOK.
    hareket(buton, 40, 40)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--hover')
    expect(halkaSinif()).not.toContain('cursor-ring--metin')

    // Gercek yazma alanlari: metin durumu + I.
    hareket(girdi, 60, 120)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--metin')
    expect(halkaSinif()).not.toContain('cursor-ring--hover')

    hareket(alan, 60, 140)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--metin')

    hareket(duzenlenebilir, 60, 160)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--metin')

    // Metin olmayan girdi tipleri (checkbox) metin durumuna GIRMEZ.
    hareket(kutu, 80, 180)
    kare()
    expect(halkaSinif()).not.toContain('cursor-ring--metin')
    expect(halkaSinif()).not.toContain('cursor-ring--hover')
  })

  it('duz metin/baslik metin durumuna GIRMEZ; caret API hic sorgulanmaz (kaldirilan tespit)', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { baslik, paragraf, hareket } = panelKur()
    // Eski kod bu API ile paragrafi metin durumuna sokuyordu (regresyon testi).
    const caretCagri = vi.fn(() => {
      const aralik = document.createRange()
      aralik.setStart(paragraf.firstChild as Node, 1)
      aralik.setEnd(paragraf.firstChild as Node, 1)
      return aralik
    })
    Object.defineProperty(document, 'caretRangeFromPoint', { configurable: true, writable: true, value: caretCagri })
    render(<CursorRing />)

    hareket(paragraf, 120, 75)
    kare()
    expect(halkaSinif()).not.toContain('cursor-ring--metin')

    hareket(baslik, 120, 45)
    kare()
    expect(halkaSinif()).not.toContain('cursor-ring--metin')
    expect(caretCagri).not.toHaveBeenCalled()
  })

  it('yazma alanindan duz metne cikis ANINDA olur (hysteresis yok)', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { panel, girdi, hareket } = panelKur()
    render(<CursorRing />)

    hareket(girdi, 60, 120)
    kare()
    expect(halkaSinif()).toContain('cursor-ring--metin')

    hareket(panel, 300, 20)
    expect(halkaSinif()).not.toContain('cursor-ring--metin')
  })

  it('I (beam) tek dugumdur ve yazma alaninda da tek kalir', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { girdi, hareket } = panelKur()
    render(<CursorRing />)

    expect(document.querySelectorAll('.cursor-ring__beam')).toHaveLength(1)
    hareket(girdi, 60, 120)
    kare()
    expect(document.querySelectorAll('.cursor-ring__beam')).toHaveLength(1)
  })

  it('mousedown tek ic-dot ile baski durumunu acar, mouseup kapatir', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 40, 40)
    kare()
    window.dispatchEvent(pointerOlay('pointerdown', 40, 40))
    expect(halkaSinif()).toContain('cursor-ring--press')
    expect(document.querySelectorAll('.cursor-ring__dot')).toHaveLength(1)

    window.dispatchEvent(pointerOlay('pointerup'))
    expect(halkaSinif()).not.toContain('cursor-ring--press')
    expect(document.querySelectorAll('.cursor-ring__dot')).toHaveLength(1)
  })

  it('basili halde 6px ustu hareket drag sikismasini acar', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 40, 40)
    kare()
    window.dispatchEvent(pointerOlay('pointerdown', 40, 40))
    hareket(buton, 52, 40)
    expect(halkaSinif()).toContain('cursor-ring--drag')

    window.dispatchEvent(pointerOlay('pointerup'))
    expect(halkaSinif()).not.toContain('cursor-ring--drag')
  })

  it('prefers-reduced-motion: lerp yok (anlik konum) ve smear kapali', () => {
    ortamKur({ isaretci: 'fine', azHareket: true })
    document.documentElement.style.setProperty('--reflect-parallax', '-0.3')
    document.documentElement.style.setProperty('--reflect-lerp', '0.15')
    document.documentElement.style.setProperty('--reflect-stretch-max', '0.2')
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 320, 180)
    kare()

    expect((halka() as HTMLElement).style.transform).toBe('translate3d(320.00px, 180.00px, 0)')
    expect(panelDegeri('--smear')).toBe('0.000')
    expect(panelDegeri('--smear-sx')).toBe('1.0000')
  })

  it('pencere kaybinda gorunurluk ve yansima degiskenleri temizlenir', () => {
    ortamKur({ isaretci: 'fine', azHareket: false })
    document.documentElement.style.setProperty('--reflect-parallax', '-0.3')
    const { buton, hareket } = panelKur()
    render(<CursorRing />)

    hareket(buton, 100, 100)
    kare()
    expect(panelDegeri('--cursor-x')).not.toBe('')

    document.documentElement.dispatchEvent(pointerOlay('pointerleave'))
    expect(halkaSinif()).not.toContain('cursor-ring--visible')
    expect(document.documentElement.classList.contains('cursor-ring-on')).toBe(false)
    kare()
    expect(panelDegeri('--cursor-x')).toBe('')
  })
})
