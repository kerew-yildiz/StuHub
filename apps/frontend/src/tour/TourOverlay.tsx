import { useCallback, useEffect, useMemo, useState } from 'react'

import { TOUR_STEPS, TOUR_STEP_TITLES, type TourLayer, type TourStep } from './steps'

interface TourOverlayProps {
  layer: TourLayer
  open: boolean
  onClose: () => void
}

/**
 * Merkezi TourController görünümü (yönerge §23-24):
 * - subtle glass + low dim/blur — kullanıcı uygulamadan kopmaz
 * - gerçek anchor vurgusu: data-tour-id elementi ring ile işaretlenir
 * - popover viewport-safe (üst/alt taşma algorithm'i §9 ile aynı)
 * - reduced-motion'da animasyonlar devre dışı (CSS)
 * - adım, anchor DOM'da yoksa sessizce atlanır
 */
export function TourOverlay({ layer, open, onClose }: TourOverlayProps) {
  const allSteps = useMemo(() => TOUR_STEPS[layer], [layer])
  const [index, setIndex] = useState(0)
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null)
  const [step, setStep] = useState<TourStep | null>(null)

  // Anchor'ı çöz: bulunamayan adımları atla.
  const resolveStep = useCallback((from: number): { step: TourStep; index: number } | null => {
    for (let i = from; i < allSteps.length; i += 1) {
      const candidate = allSteps[i]
      if (document.querySelector(`[data-tour-id="${candidate.anchor}"]`)) {
        return { step: candidate, index: i }
      }
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
    const updateRect = () => {
      const previous = document.querySelector('.tour-target')
      if (previous) previous.classList.remove('tour-target')
      const el = document.querySelector(`[data-tour-id="${step.anchor}"]`)
      if (el) {
        el.classList.add('tour-target')
        el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        setAnchorRect(el.getBoundingClientRect())
      } else {
        setAnchorRect(null)
      }
    }
    updateRect()
    window.addEventListener('resize', updateRect)
    window.addEventListener('scroll', updateRect, true)
    return () => {
      window.removeEventListener('resize', updateRect)
      window.removeEventListener('scroll', updateRect, true)
      const previous = document.querySelector('.tour-target')
      if (previous) previous.classList.remove('tour-target')
    }
  }, [open, step])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight') setIndex((v) => Math.min(v + 1, allSteps.length - 1))
      if (event.key === 'ArrowLeft') setIndex((v) => Math.max(v - 1, 0))
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, allSteps.length])

  if (!open || !step) return null

  const next = () => {
    const found = resolveStep(index + 1)
    if (found) {
      setStep(found.step)
      setIndex(found.index)
    } else {
      // Sonraki adımların hepsi anchor'sız → turu bitir.
      onClose()
    }
  }

  const prev = () => {
    for (let i = index - 1; i >= 0; i -= 1) {
      if (document.querySelector(`[data-tour-id="${allSteps[i].anchor}"]`)) {
        setStep(allSteps[i])
        setIndex(i)
        return
      }
    }
  }

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

  return (
    <>
      {/* Low dim — current target görünürlüğü korunur (§23) */}
      <div className="tour-overlay" role="presentation" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="false"
        aria-label={TOUR_STEP_TITLES[layer]}
        className="tour-popover"
        style={{ top, left, width: POPOVER_WIDTH }}
      >
        <p className="eyebrow">{TOUR_STEP_TITLES[layer]}</p>
        <h2 className="mt-2 text-lg font-semibold">{step.title}</h2>
        <p className="mt-2 text-sm leading-6 text-stuhub-text-secondary">{step.body}</p>
        <div className="mt-5 flex items-center justify-between">
          <span className="text-xs text-stuhub-text-muted">{index + 1} / {allSteps.length}</span>
          <div className="flex gap-2">
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
    </>
  )
}
