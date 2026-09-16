import { useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { TourOverlay } from './TourOverlay'
import type { TourLayer } from './steps'

/**
 * Layer-aware TourController (yönerge §24): tur adımları feature-specific
 * registry'den gelir; current route → layer eşlemesi merkezi burada yapılır.
 * Hardcoded tooltip'ler app'e dağılmaz.
 */
export function useTourController() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [layer, setLayer] = useState<TourLayer>('global')

  const layerFromPath = useCallback((): TourLayer => {
    if (/^\/dersler\/\d+\/defter\/\d+/.test(location.pathname)) return 'chapter'
    if (/^\/dersler\/\d+/.test(location.pathname)) return 'course'
    if (/^\/donemler\/\d+/.test(location.pathname)) return 'term'
    return 'global'
  }, [location.pathname])

  // Route değişince açık turu kapat — tur hep "current application context"te çalışır.
  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  const start = useCallback(() => {
    setLayer(layerFromPath())
    setOpen(true)
  }, [layerFromPath])

  const controller = { open, layer, start, close: () => setOpen(false) }

  return {
    controller,
    overlay: (
      <TourOverlay
        key={`${controller.layer}-${controller.open}`}
        layer={controller.layer}
        open={controller.open}
        onClose={controller.close}
      />
    ),
  }
}
