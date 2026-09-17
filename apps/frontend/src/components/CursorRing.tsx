import { useEffect, useRef, useState } from 'react'

// Glass imlec halkasi + cam yansimasi (kullanici onayli ozellik).
// - pointer:fine olmayan ortamda (dokunmatik) HIC mount edilmez.
// - Tum kare-basi yazimlar TEK rAF dongusunde: halka translate3d; yansima ise
//   panel-yerel CSS degiskenleri (--cursor-x/y, --edge-*, --smear*). Layout
//   okuyan/yazan islem yok; getBoundingClientRect yalniz panel DEGISTIGINDE.
// - T1 ters-paralaks + T2 kenar isigi + T3 hiz smear'i CSS degiskenleriyle
//   ayarlanir (--reflect-*); degerler panel degisiminde BIR KEZ okunur.
// - prefers-reduced-motion: halka lerp'i ve T3 (smear/gecikme) kapali, konum anlik.

const INTERACTIVE_SELECTOR = 'a,button,[role=button],select,[data-interactive]'
// I (beam) YALNIZ gercek yazma alanlarinda: metin girdisi olan input tipleri,
// textarea ve contenteditable. Duz metin (baslik/paragraf/liste/kart icerigi/
// not govdesi/sohbet balonu) imleci DEGISTIRMEZ — geometrik caret testi
// (caretRangeFromPoint) kaldirildi (2026-09-17 kullanici istegi).
const EDITABLE_SELECTOR =
  'textarea,[contenteditable=""],[contenteditable="true"],' +
  'input:not([type=button]):not([type=submit]):not([type=reset]):not([type=image]):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]):not([type=file])'
const PANEL_SELECTOR = '.glass-panel'
const LERP = 0.34
const SETTLE_EPSILON = 0.1
const DRAG_THRESHOLD = 6
const SMEAR_FULL_SPEED = 2 // px/ms — bu hizda smear doygunlasir

type ReflectConfig = {
  lerp: number
  parallax: number
  edgeRange: number
  stretchMax: number
}

export function CursorRing() {
  const [fine, setFine] = useState(() => window.matchMedia('(pointer: fine)').matches)

  useEffect(() => {
    const mq = window.matchMedia('(pointer: fine)')
    const sync = () => setFine(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  return fine ? <CursorRingLayer /> : null
}

function CursorRingLayer() {
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const html = document.documentElement
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')

    let raf = 0
    let tx = 0
    let ty = 0
    let cx = 0
    let cy = 0
    let hx = 0 // yansima (T1) konumu — kendi gecikmesiyle
    let hy = 0
    let oncekiX = 0
    let oncekiY = 0
    let sonT = 0
    let hiz = 0 // px/ms (son kare) — T3 smear girdisi
    let kareDx = 0
    let kareDy = 0
    let kareMesafe = 0
    let sonHareket = 0 // son pointer hareketi (rAF uykusu icin)
    let yazilanX = Number.NaN // olu bolge: son yazilan halka konumu
    let yazilanY = Number.NaN
    let varX = Number.NaN // olu bolge: son yazilan panel degiskeni (tam sayi)
    let varY = Number.NaN
    let kareNo = 0 // yansima guncelleme kadansi (2 karede bir)
    let visible = false
    let down = false
    let dragging = false
    let startX = 0
    let startY = 0
    let hoverPanel: HTMLElement | null = null
    let paintedPanel: HTMLElement | null = null
    let cfg: ReflectConfig = { lerp: 1, parallax: 0, edgeRange: 0, stretchMax: 0 }

    const sayi = (ad: string, varsayilan: number) => {
      const v = Number.parseFloat(getComputedStyle(html).getPropertyValue(ad))
      return Number.isFinite(v) ? v : varsayilan
    }
    const readConfig = () => {
      cfg = {
        lerp: sayi('--reflect-lerp', 1),
        parallax: sayi('--reflect-parallax', 0),
        edgeRange: sayi('--reflect-edge-range', 0),
        stretchMax: sayi('--reflect-stretch-max', 0),
      }
    }

    const clearPanelVars = (panel: HTMLElement | null) => {
      if (!panel) return
      for (const ad of ['--cursor-x', '--cursor-y', '--edge-t', '--edge-b', '--edge-l', '--edge-r', '--smear', '--smear-sx', '--smear-sy']) {
        panel.style.removeProperty(ad)
      }
      // A: yansima katmani yalniz AKTIF panelde kalsin (ekranda en fazla 1).
      panel.removeAttribute('data-reflect')
      varX = Number.NaN
      varY = Number.NaN
    }

    const kirpil = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v)

    const paint = (zorlaYansima: boolean) => {
      // Olu bolge (C): 0.4px alti degisimde yazim atlanir (bos style invalidation yok).
      if (!(Math.abs(cx - yazilanX) < 0.4 && Math.abs(cy - yazilanY) < 0.4)) {
        root.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`
        yazilanX = cx
        yazilanY = cy
      }
      const panelDegisti = paintedPanel !== hoverPanel
      if (panelDegisti) {
        clearPanelVars(paintedPanel)
        paintedPanel = hoverPanel
        paintedPanel?.setAttribute('data-reflect', '1')
        readConfig()
      }
      if (!paintedPanel) return
      // C2: yansima 2 karede bir guncellenir (~30 fps). Highlight zaten lerp ile
      // gecikmeli; gozle fark yok, gradient yeniden rasterizasyonu yariya iner.
      if (!zorlaYansima && !panelDegisti && kareNo % 2 === 1) return
      const rect = paintedPanel.getBoundingClientRect()
      const left = rect.left + paintedPanel.clientLeft
      const top = rect.top + paintedPanel.clientTop
      const gen = rect.width
      const yuk = rect.height
      const imlecX = tx - left
      const imlecY = ty - top
      // T1: ters-paralaks (panel merkezine dogru -k) — leke imlecin ALTINDA dogmaz.
      const lekeX = gen / 2 + (hx - left - gen / 2) * cfg.parallax
      const lekeY = yuk / 2 + (hy - top - yuk / 2) * cfg.parallax
      // T3: hiz smear'i — hareket ekseninde hafif uzama; merkez telafi edilir.
      const s = reduce.matches ? 0 : kirpil(hiz / SMEAR_FULL_SPEED)
      const yonX = kareMesafe > 0 ? Math.abs(kareDx) / kareMesafe : 0
      const yonY = kareMesafe > 0 ? Math.abs(kareDy) / kareMesafe : 0
      const sx = 1 + s * cfg.stretchMax * yonX
      const sy = 1 + s * cfg.stretchMax * yonY
      const lekeSayi = [Math.round(gen / 2 + (lekeX - gen / 2) / sx), Math.round(yuk / 2 + (lekeY - yuk / 2) / sy)]
      if (lekeSayi[0] !== varX || lekeSayi[1] !== varY) {
        paintedPanel.style.setProperty('--cursor-x', String(lekeSayi[0]))
        paintedPanel.style.setProperty('--cursor-y', String(lekeSayi[1]))
        varX = lekeSayi[0]
        varY = lekeSayi[1]
      }
      paintedPanel.style.setProperty('--smear', s.toFixed(3))
      paintedPanel.style.setProperty('--smear-sx', sx.toFixed(4))
      paintedPanel.style.setProperty('--smear-sy', sy.toFixed(4))
      // T2: hangi kenara yakinsa o kenar parlar (mesafeyle soner).
      const mesafe = (d: number) => (cfg.edgeRange > 0 ? (1 - d / cfg.edgeRange) : 0)
      const guc = (d: number) => { const v = kirpil(mesafe(d)); return (v * v).toFixed(3) }
      paintedPanel.style.setProperty('--edge-t', guc(imlecY))
      paintedPanel.style.setProperty('--edge-b', guc(yuk - imlecY))
      paintedPanel.style.setProperty('--edge-l', guc(imlecX))
      paintedPanel.style.setProperty('--edge-r', guc(gen - imlecX))
    }

    const tick = (t: number) => {
      raf = 0
      const dt = sonT ? Math.max(1, t - sonT) : 16
      sonT = t
      kareDx = tx - oncekiX
      kareDy = ty - oncekiY
      kareMesafe = Math.hypot(kareDx, kareDy)
      hiz = kareMesafe / dt
      oncekiX = tx
      oncekiY = ty
      if (reduce.matches) {
        cx = tx
        cy = ty
        hx = tx
        hy = ty
      } else {
        cx += (tx - cx) * LERP
        cy += (ty - cy) * LERP
        hx += (tx - hx) * cfg.lerp
        hy += (ty - hy) * cfg.lerp
      }
      const durgunHalka = Math.abs(tx - cx) <= SETTLE_EPSILON && Math.abs(ty - cy) <= SETTLE_EPSILON
      const durgunLeke = Math.abs(tx - hx) <= SETTLE_EPSILON && Math.abs(ty - hy) <= SETTLE_EPSILON
      // C: 200 ms hareketsizlikte hedefe otur ve donguyu UYUT (pointermove uyandirir).
      const uyku = t - sonHareket > 200 && Math.abs(tx - cx) < 2 && Math.abs(ty - cy) < 2
      if (durgunHalka || uyku) {
        cx = tx
        cy = ty
      }
      if (durgunLeke || uyku) {
        hx = tx
        hy = ty
      }
      if (durgunHalka && durgunLeke) hiz = 0
      if (uyku) hiz = 0
      kareNo += 1
      paint(uyku || (durgunHalka && durgunLeke))
      if (!uyku && (!durgunHalka || !durgunLeke)) raf = requestAnimationFrame(tick)
      else sonT = 0
    }

    const kick = () => {
      if (!raf) raf = requestAnimationFrame(tick)
    }

    const setVisible = (next: boolean) => {
      if (visible === next) return
      visible = next
      root.classList.toggle('cursor-ring--visible', next)
      // cursor:none + cam yansimasi yalnizca imlec penceredeyken aktif (CSS kapi sinifi).
      html.classList.toggle('cursor-ring-on', next)
      if (!next) {
        clearPanelVars(paintedPanel)
        paintedPanel = null
        hoverPanel = null
      }
    }

    const onMove = (event: PointerEvent) => {
      sonHareket = performance.now()
      tx = event.clientX
      ty = event.clientY
      const target = event.target instanceof Element ? event.target : null
      hoverPanel = target?.closest<HTMLElement>(PANEL_SELECTOR) ?? null
      const etkilesimli = target?.closest(INTERACTIVE_SELECTOR)
      root.classList.toggle('cursor-ring--hover', Boolean(etkilesimli))
      // Oncelik: (a) etkilesimli > (b) yazma alani. I (beam) yalniz yazma
      // alaninda acilir; duz metin uzerinde imlec DEGISMEZ (geometrik caret
      // testi kaldirildi — sinirda titreme kaynagi da onunla gitti).
      root.classList.toggle('cursor-ring--metin', !etkilesimli && Boolean(target?.closest(EDITABLE_SELECTOR)))
      if (down) {
        if (!dragging && Math.hypot(event.clientX - startX, event.clientY - startY) > DRAG_THRESHOLD) dragging = true
        root.classList.toggle('cursor-ring--drag', dragging)
      }
      if (!visible) {
        setVisible(true)
        cx = tx
        cy = ty
        hx = tx
        hy = ty
      }
      kick()
    }

    const onDown = (event: PointerEvent) => {
      sonHareket = performance.now()
      down = true
      dragging = false
      startX = event.clientX
      startY = event.clientY
      if (!visible) {
        tx = event.clientX
        ty = event.clientY
        cx = tx
        cy = ty
        hx = tx
        hy = ty
        setVisible(true)
        kick()
      }
      root.classList.add('cursor-ring--press')
    }

    const onUp = () => {
      down = false
      dragging = false
      root.classList.remove('cursor-ring--press', 'cursor-ring--drag')
    }

    const onLeave = () => setVisible(false)

    const onScroll = () => {
      if (!visible) return
      sonHareket = performance.now()
      const el = document.elementFromPoint(tx, ty)
      hoverPanel = el?.closest<HTMLElement>(PANEL_SELECTOR) ?? null
      kick()
    }

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    window.addEventListener('pointerup', onUp, { passive: true })
    window.addEventListener('pointercancel', onUp, { passive: true })
    window.addEventListener('blur', onLeave)
    html.addEventListener('pointerleave', onLeave)
    document.addEventListener('scroll', onScroll, { capture: true, passive: true })
    readConfig()

    return () => {
      if (raf) cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      window.removeEventListener('blur', onLeave)
      html.removeEventListener('pointerleave', onLeave)
      document.removeEventListener('scroll', onScroll, { capture: true })
      root.classList.remove('cursor-ring--visible', 'cursor-ring--hover', 'cursor-ring--metin', 'cursor-ring--press', 'cursor-ring--drag')
      html.classList.remove('cursor-ring-on')
      clearPanelVars(paintedPanel)
      hoverPanel?.removeAttribute('data-reflect')
    }
  }, [])

  return (
    <div ref={rootRef} className="cursor-ring" aria-hidden="true">
      <span className="cursor-ring__ring" />
      <span className="cursor-ring__beam" />
      <span className="cursor-ring__dot" />
    </div>
  )
}
