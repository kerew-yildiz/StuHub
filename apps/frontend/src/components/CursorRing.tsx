import { useEffect, useRef, useState } from 'react'

// Glass cursor ring + ONE global ambient cursor glow (2026-09-19 performance pass).
// - pointer:fine olmayan ortamda (dokunmatik) HIC mount edilmez.
// - Tum kare-basi yazimlar TEK rAF dongusunda: kok katman (halka + glow)
//   translate3d ile tasinir. Layout okuyan/yazan islem YOK — panel yansima
//   sistemi (data-reflect + --cursor-x/y + --edge-* + --smear*) kaldirildi;
//   glow tek bir komposit katmandir, kare basi CSS degiskeni yazmaz.
// - prefers-reduced-motion: halka lerp'i kapali, konum anlik.

const INTERACTIVE_SELECTOR = 'a,button,[role=button],select,[data-interactive]'
// I (beam) YALNIZ gercek yazma alanlarinda: metin girdisi olan input tipleri,
// textarea ve contenteditable. Duz metin (baslik/paragraf/liste/kart icerigi/
// not govdesi/sohbet balonu) imleci DEGISTIRMEZ — geometrik caret testi
// (caretRangeFromPoint) kaldirildi (2026-09-17 kullanici istegi).
const EDITABLE_SELECTOR =
  'textarea,[contenteditable=""],[contenteditable="true"],' +
  'input:not([type=button]):not([type=submit]):not([type=reset]):not([type=image]):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]):not([type=file])'
const LERP = 0.34
const SETTLE_EPSILON = 0.1
const DRAG_THRESHOLD = 6

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
    let sonHareket = 0 // son pointer hareketi (rAF uykusu icin)
    let yazilanX = Number.NaN // olu bolge: son yazilan konum
    let yazilanY = Number.NaN
    let visible = false
    let down = false
    let dragging = false
    let startX = 0
    let startY = 0

    const paint = () => {
      // Olu bolge: 0.4px alti degisimde yazim atlanir (bos style invalidation yok).
      if (!(Math.abs(cx - yazilanX) < 0.4 && Math.abs(cy - yazilanY) < 0.4)) {
        root.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`
        yazilanX = cx
        yazilanY = cy
      }
    }

    const tick = (t: number) => {
      raf = 0
      if (reduce.matches) {
        cx = tx
        cy = ty
      } else {
        cx += (tx - cx) * LERP
        cy += (ty - cy) * LERP
      }
      const durgun = Math.abs(tx - cx) <= SETTLE_EPSILON && Math.abs(ty - cy) <= SETTLE_EPSILON
      // C: 200 ms hareketsizlikte hedefe otur ve donguyu UYUT (pointermove uyandirir).
      const uyku = t - sonHareket > 200 && Math.abs(tx - cx) < 2 && Math.abs(ty - cy) < 2
      if (durgun || uyku) {
        cx = tx
        cy = ty
      }
      paint()
      if (!uyku && !durgun) raf = requestAnimationFrame(tick)
    }

    const kick = () => {
      if (!raf) raf = requestAnimationFrame(tick)
    }

    const setVisible = (next: boolean) => {
      if (visible === next) return
      visible = next
      root.classList.toggle('cursor-ring--visible', next)
      // cursor:none + glow yalnizca imlec penceredeyken aktif (CSS kapi sinifi).
      html.classList.toggle('cursor-ring-on', next)
    }

    const onMove = (event: PointerEvent) => {
      sonHareket = performance.now()
      tx = event.clientX
      ty = event.clientY
      const target = event.target instanceof Element ? event.target : null
      const etkilesimli = target?.closest(INTERACTIVE_SELECTOR)
      root.classList.toggle('cursor-ring--hover', Boolean(etkilesimli))
      // Oncelik: (a) etkilesimli > (b) yazma alani. I (beam) yalniz yazma
      // alaninda acilir; duz metin uzerinde imlec DEGISMEZ.
      root.classList.toggle('cursor-ring--metin', !etkilesimli && Boolean(target?.closest(EDITABLE_SELECTOR)))
      if (down) {
        if (!dragging && Math.hypot(event.clientX - startX, event.clientY - startY) > DRAG_THRESHOLD) dragging = true
        root.classList.toggle('cursor-ring--drag', dragging)
      }
      if (!visible) {
        setVisible(true)
        cx = tx
        cy = ty
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

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    window.addEventListener('pointerup', onUp, { passive: true })
    window.addEventListener('pointercancel', onUp, { passive: true })
    window.addEventListener('blur', onLeave)
    html.addEventListener('pointerleave', onLeave)

    return () => {
      if (raf) cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      window.removeEventListener('blur', onLeave)
      html.removeEventListener('pointerleave', onLeave)
      root.classList.remove('cursor-ring--visible', 'cursor-ring--hover', 'cursor-ring--metin', 'cursor-ring--press', 'cursor-ring--drag')
      html.classList.remove('cursor-ring-on')
    }
  }, [])

  return (
    <div ref={rootRef} className="cursor-ring" aria-hidden="true">
      <span className="cursor-glow" />
      <span className="cursor-ring__ring" />
      <span className="cursor-ring__beam" />
      <span className="cursor-ring__dot" />
    </div>
  )
}
