import { create } from 'zustand'

interface HelpStore {
  open: boolean
  toggle: () => void
  close: () => void
}

/** Yardım panelinin açık/kapalı durumu — header'daki "?" butonu ve global "?"
 * kısayolu aynı store üzerinden konuşur. */
export const useHelpStore = create<HelpStore>((set) => ({
  open: false,
  toggle: () => set((s) => ({ open: !s.open })),
  close: () => set({ open: false }),
}))
