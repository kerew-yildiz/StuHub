import { create } from 'zustand'

/**
 * Global toast sistemi (P3 — Visual Excellence).
 *
 * Kullanım: `const toast = useToastStore(s => s.toast); toast.success('Kaydedildi')`
 * ToastHost app kökünde render edilir; roller: success / error / info.
 * Hata toast'ları kullanıcı kapatana kadar kalır; aria-live ile duyurulur.
 */

export type ToastKind = 'success' | 'error' | 'info'

/** Toast üzerindeki eylem düğmesi (ör. "Yeni sürüm hazır → Yenile"). */
export interface ToastAction {
  label: string
  onClick: () => void
}

export interface Toast {
  id: number
  kind: ToastKind
  message: string
  /** Varsa toast KALICIDIR (otomatik kapanmaz) ve düğme gösterir — kullanıcı kararı. */
  action?: ToastAction
}

interface ToastState {
  toasts: Toast[]
  toast: (kind: ToastKind, message: string, action?: ToastAction) => void
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  toast: (kind, message, action) => {
    const id = nextId++
    set((s) => ({ toasts: [...s.toasts, { id, kind, message, action }] }))
    if (kind !== 'error' && !action) {
      // success/info otomatik kapanır (4.2s — okuma süresi + çıkış payı)
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
      }, 4200)
    }
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

/** Imperative kolay erişim — hook dışından da çağrılabilir (api katmanı vb.). */
export const toast = {
  success: (message: string, action?: ToastAction) =>
    useToastStore.getState().toast('success', message, action),
  error: (message: string, action?: ToastAction) =>
    useToastStore.getState().toast('error', message, action),
  info: (message: string, action?: ToastAction) =>
    useToastStore.getState().toast('info', message, action),
}
