import { create } from 'zustand'

interface ConfirmState {
  open: boolean
  message: string
  resolve: ((value: boolean) => void) | null
}

interface ConfirmStore extends ConfirmState {
  /** Bileşen dışından da çağrılabilir — `window.confirm` yerine geçer. */
  request: (message: string) => Promise<boolean>
  respond: (value: boolean) => void
}

export const useConfirmStore = create<ConfirmStore>((set, get) => ({
  open: false,
  message: '',
  resolve: null,
  request: (message) =>
    new Promise<boolean>((resolve) => {
      set({ open: true, message, resolve })
    }),
  respond: (value) => {
    get().resolve?.(value)
    set({ open: false, message: '', resolve: null })
  },
}))

/**
 * Yıkıcı eylemler öncesi tema uyumlu onay diyaloğu — tarayıcının kendi
 * `window.confirm()`'ü CSS ile stillenemediği için (bkz. `ConfirmDialog.tsx`).
 * `<ConfirmDialog />` App kökünde bir kez render edilir.
 */
export function confirmDialog(message: string): Promise<boolean> {
  return useConfirmStore.getState().request(message)
}
