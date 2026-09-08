import { create } from 'zustand'

interface PaletteStore {
  open: boolean
  toggle: () => void
  close: () => void
}

/** Komut paletinin açık/kapalı durumu — header'daki "Ara" butonu ve global
 * Ctrl/Cmd+K kısayolu aynı store üzerinden konuşur. */
export const usePaletteStore = create<PaletteStore>((set) => ({
  open: false,
  toggle: () => set((s) => ({ open: !s.open })),
  close: () => set({ open: false }),
}))
