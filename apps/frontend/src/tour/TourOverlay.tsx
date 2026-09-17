import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'

import { TOUR_STEPS, TOUR_STEP_TITLES, type TourLayer, type TourStep } from './steps'
import { useTourStore } from './tourStore'

interface TourOverlayProps {
  layer: TourLayer
  open: boolean
  onClose: () => void
}

/**
 * Rehberli tur görünümü:
 * - BODY'ye portal: tur ağacı header'ın (backdrop-filter'lı) içinde kalınca fixed
 *   çocuklar header kutusuna hapsoluyordu — dim yalnız header şeridini kaplıyor,
 *   popover anchor'a göre kayıyordu.
 * - spotlight: dim TEK elemanın dev box-shadow'udur (hedefin kutusu boş kalır);
 *   halka hedefin kendi ::after'ında değil bu katmanda çizilir → hedef hangi
 *   stacking context'te olursa olsun vurgu dim'in üstünde kalır.
 * - adım çözümü: anchor'ı DOM'da olan adım spotlight'lanır; anchor'ı olmayan
 *   rota adımı kullanıcıyı gerçek sayfaya taşır (popover spotlightsız).
 * - adım geçişi: popover ve spotlight yeni anchor'a KONUM GEÇİŞİ ile taşınır
 *   (transform, --duration-state) — ilk yerleşim (açılış) animasyonsuz.
 * - İleri / Geri / Kapat + Escape kapatır; son adımda "Turu bitir" turu kapatır.
 * - reduced-motion'da geçiş yok (anlık konum).
 */
export function TourOverlay({ layer, open, onClose }: TourOverlayProps) {
  const allSteps = useMemo(() => TOUR_STEPS[layer], [layer])
  const [index, setIndex] = useState(0)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const [step, setStep] = useState<TourStep | null>(null)
  // Konum geçişi yalnız adım değişiminde olsun: ilk yerleşimden sonraki karede açılır,
  // aksi halde açılışta popover viewport ortasından anchor'a "süzülürdü".
  const [gecisHazir, setGecisHazir] = useState(false)
  const [azHareket] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  const navigate = useNavigate()
  const { pathname } = useLocation()

  // Anchor'ı çöz: bulunamayan adımları atla; rota adımı (anchor'sız) atlanmaz.
  const resolveStep = useCallback((from: number): { step: TourStep; index: number } | null => {
    for (let i = from; i < allSteps.length; i += 1) {
      const candidate = allSteps[i]
      const anchorVar = candidate.anchor
        ? document.querySelector(`[data-tour-id="${candidate.anchor}"]`)
        : null
      if (anchorVar || candidate.route) return { step: candidate, index: i }
    }
    return null
  }, [allSteps])

  useEffect(() => {
    if (!open) return
    const found = resolveStep(0)
    if (!found) {
      onClose()
      return
    }
    setStep(found.step)
    setIndex(found.index)
  }, [open, resolveStep, onClose])

  useEffect(() => {
    if (!open || !step) return
    const previous = document.querySelector('.tour-target')
    if (previous) previous.classList.remove('tour-target')
    const el = step.anchor ? document.querySelector<HTMLElement>(`[data-tour-id="${step.anchor}"]`) : null
    if (!el) {
      // Spotlight yok: dim tüm viewport'u kaplar. Rota adımıysa kullanıcıyı
      // gerçek sayfaya taşı — işaret ÖNCE yazılır, TourController bu gezinmeyi
      // "tur kaynaklı" bilip turu kapatmasın.
      setAnchorRect(null)
      if (step.route && pathname !== step.route) {
        useTourStore.getState().hedefRotaAyarla(step.route)
        navigate(step.route)
      }
      return
    }
    el.classList.add('tour-target')
    const updateRect = () => setAnchorRect(el.getBoundingClientRect())
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    updateRect()
    window.addEventListener('resize', updateRect)
    window.addEventListener('scroll', updateRect, true)
    return () => {
      window.removeEventListener('resize', updateRect)
      window.removeEventListener('scroll', updateRect, true)
      el.classList.remove('tour-target')
    }
  }, [open, step, pathname, navigate])

  const next = useCallback(() => {
    const found = resolveStep(index + 1)
    if (found) {
      setStep(found.step)
      setIndex(found.index)
      return
    }
    // Sonraki adım yok → tur bitti: temiz kapanış.
    onClose()
  }, [index, resolveStep, onClose])

  // Geri yalnız spotlight'lı adımlara döner — rota adımına dönmek kullanıcıyı
  // yeniden sayfa değiştirmeye zorlardı.
  const prev = useCallback(() => {
    for (let i = index - 1; i >= 0; i -= 1) {
      const candidate = allSteps[i]
      if (candidate.anchor && document.querySelector(`[data-tour-id="${candidate.anchor}"]`)) {
        setStep(candidate)
        setIndex(i)
        return
      }
    }
  }, [index, allSteps])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      else if (event.key === 'ArrowRight') next()
      else if (event.key === 'ArrowLeft') prev()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, next, prev])

  useEffect(() => {
    if (!anchorRect || gecisHazir) return
    const raf = requestAnimationFrame(() => setGecisHazir(true))
    return () => cancelAnimationFrame(raf)
  }, [anchorRect, gecisHazir])

  if (!open || !step) return null

  // Popover konumu: anchor'ın sağına/altına, viewport-safe.
  const POPOVER_WIDTH = 340
  const MARGIN = 12
  const vw = window.innerWidth
  const vh = window.innerHeight
  let top = (anchorRect?.bottom ?? vh / 2) + 10
  let left = anchorRect ? anchorRect.right + 12 : vw / 2 - POPOVER_WIDTH / 2
  if (left + POPOVER_WIDTH + MARGIN > vw) left = Math.max(MARGIN, (anchorRect?.left ?? vw / 2) - POPOVER_WIDTH - 12)
  if (left + POPOVER_WIDTH + MARGIN > vw) left = MARGIN
  top = Math.min(Math.max(top, MARGIN), vh - 240)
  if (anchorRect && anchorRect.bottom + 240 > vh) top = Math.max(MARGIN, anchorRect.top - 250)

  // Spotlight kutusu: hedefin 4px dışına taşan, yuvarlatılmış delik.
  const spot = anchorRect
    ? {
        left: Math.round(anchorRect.left) - 4,
        top: Math.round(anchorRect.top) - 4,
        width: Math.round(anchorRect.width) + 8,
        height: Math.round(anchorRect.height) + 8,
      }
    : null

  const GECIS = gecisHazir && !azHareket
  const konumGecisi = 'transform var(--duration-state) var(--ease-out-expo)'

  return createPortal(
    <>
      <div className="tour-overlay" role="presentation" onClick={onClose} />
      <span
        aria-hidden="true"
        className={`tour-spot${spot ? '' : ' tour-spot--full'}`}
        style={
          spot
            ? {
                width: spot.width,
                height: spot.height,
                transform: `translate3d(${spot.left}px, ${spot.top}px, 0)`,
                transition: GECIS
                  ? `${konumGecisi}, width var(--duration-state) var(--ease-out-expo), height var(--duration-state) var(--ease-out-expo)`
                  : undefined,
              }
            : undefined
        }
      />
      <div
        role="dialog"
        aria-modal="false"
        aria-label={TOUR_STEP_TITLES[layer]}
        className="tour-popover"
        style={{
          top: 0,
          left: 0,
          width: POPOVER_WIDTH,
          // Konum transform ile verilir: adım geçişinde top/left değişimi layout
          // tetiklerdi (kayma/uzun kare) — transform compositor'da taşınır.
          transform: `translate3d(${left}px, ${top}px, 0)`,
          transition: GECIS ? konumGecisi : undefined,
        }}
      >
        <p className="eyebrow">{TOUR_STEP_TITLES[layer]}</p>
        <h2 className="mt-2 text-lg font-semibold">{step.title}</h2>
        <p className="mt-2 text-sm leading-6 text-stuhub-text-secondary">{step.body}</p>
        <div className="mt-5 flex items-center justify-between gap-2">
          <span className="text-xs text-stuhub-text-muted">{index + 1} / {allSteps.length}</span>
          <div className="flex items-center gap-2">
            <button type="button" className="tour-popover__kapat" onClick={onClose}>
              Kapat
            </button>
            {index > 0 && (
              <button type="button" className="glass-panel-subtle glass-interactive rounded-control px-3 py-1.5 text-sm text-stuhub-text-secondary" onClick={prev}>
                Geri
              </button>
            )}
            <button type="button" className="btn-primary" onClick={next} autoFocus>
              {step.actionLabel}
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body,
  )
}
