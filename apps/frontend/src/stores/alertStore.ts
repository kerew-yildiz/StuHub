import { create } from 'zustand'

interface AlertState {
  open: boolean
  message: string
  resolve: (() => void) | null
}

interface AlertStore extends AlertState {
  /** Bileşen dışından da çağrılabilir — `window.alert` yerine geçer. */
  request: (message: string) => Promise<void>
  respond: () => void
}

export const useAlertStore = create<AlertStore>((set, get) => ({
  open: false,
  message: '',
  resolve: null,
  request: (message) =>
    new Promise<void>((resolve) => {
      set({ open: true, message, resolve })
    }),
  respond: () => {
    get().resolve?.()
    set({ open: false, message: '', resolve: null })
  },
}))

/**
 * Tema uyumlu tek-butonlu bilgi diyaloğu — `window.alert()` yerine. Özellikle bir
 * üretim ön koşulu karşılanmadığında (ör. "önce not oluştur") kullanıcıya küçük,
 * gözden kaçabilecek bir satır yerine dikkat çekici bir mesaj göstermek için
 * (bkz. `generationStore.ts` `finishJob`, `GuidePanel.tsx` `handleGenerate`).
 * `<AlertDialog />` App kökünde bir kez render edilir.
 */
export function alertDialog(message: string): Promise<void> {
  return useAlertStore.getState().request(message)
}
