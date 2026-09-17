import { useEffect, useMemo } from 'react'
import { useLocation } from 'react-router-dom'

import { TourOverlay } from './TourOverlay'
import { startHelpTour, useTourStore } from './tourStore'

/**
 * TourController (yönerge §24): tur açık/kapalı durumu ve katmanı MERKEZİ
 * store'da yaşar (tourStore) — böylece turu yalnız header değil, herhangi bir
 * bileşen `startHelpTour()` ile başlatabilir (dışa açık stabil API).
 * Bu hook yalnız görünümü bağlar: store'dan okur, overlay'i render eder.
 */
export function useTourController() {
  const location = useLocation()
  const open = useTourStore((s) => s.open)
  const layer = useTourStore((s) => s.layer)
  const oturum = useTourStore((s) => s.oturum)

  // Rota değişince açık turu kapat — tur hep "current application context"te
  // çalışır. İSTİSNA: turun KENDİ adımı için gittiği rota (adım `route` taşır)
  // kapatma sayılmaz; tur yeni bağlamda devam eder.
  useEffect(() => {
    const store = useTourStore.getState()
    if (!store.open) return
    if (store.hedefRota === location.pathname) {
      store.hedefRotaAyarla(null)
      return
    }
    store.close()
  }, [location.pathname])

  const controller = useMemo(
    () => ({ open, layer, start: startHelpTour, close: () => useTourStore.getState().close() }),
    [open, layer],
  )

  return {
    controller,
    overlay: (
      <TourOverlay
        key={`${layer}-${oturum}`}
        layer={layer}
        open={open}
        onClose={controller.close}
      />
    ),
  }
}
