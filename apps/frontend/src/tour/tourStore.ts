import { create } from 'zustand'

import { layerFromPath, type TourLayer } from './steps'

interface TourStore {
  open: boolean
  layer: TourLayer
  /**
   * Turun KENDİ adımı için gittiği rota. TourController rota değişiminde turu
   * kapatır (tur hep "current application context"te çalışır); bu işaret
   * tur-kaynaklı gezinmeyi kapatma saymaz. null = tur gezinmedi.
   */
  hedefRota: string | null
  /**
   * Tur oturumu: her start() ile artar. Overlay bu sayacı key olarak taşır —
   * "Kurtarma turu başlat" gibi bir buton tur AÇIKKEN tekrar basılırsa tur
   * baştan başlar (1. adım), yarım kalmış yerden devam etmez.
   */
  oturum: number
  start: (layer: TourLayer) => void
  close: () => void
  hedefRotaAyarla: (rota: string | null) => void
}

export const useTourStore = create<TourStore>((set) => ({
  open: false,
  layer: 'global',
  hedefRota: null,
  oturum: 0,
  start: (layer) => set((s) => ({ open: true, layer, hedefRota: null, oturum: s.oturum + 1 })),
  close: () => set({ open: false, hedefRota: null }),
  hedefRotaAyarla: (rota) => set({ hedefRota: rota }),
}))

/**
 * Dışa açık stabil API: rehberli turu HERHANGİ bir bileşenden başlatır (üst bardaki
 * `?` ve yardım panelindeki "Adım adım turu başlat" bunu çağırır). Katman aktif
 * rotadan türetilir; çağıran taraf turun nerede/nasıl render edildiğini bilmez.
 * Rota dışında bir argüman almaz — sözleşme bilinçli olarak dar.
 */
export function startHelpTour() {
  useTourStore.getState().start(layerFromPath(window.location.pathname))
}

/** Açık turu kapatır (tur yoksa no-op). */
export function stopHelpTour() {
  useTourStore.getState().close()
}

/** Tur açık mı — panel gibi başka yüzeyler katman çakışmasını buna bakarak önler. */
export function useHelpTourOpen() {
  return useTourStore((s) => s.open)
}
