import { create } from 'zustand'

/**
 * Global toast sistemi (P3 — Visual Excellence).
 *
 * Kullanım: `const toast = useToastStore(s => s.toast); toast.success('Kaydedildi')`
 * ToastHost app kökünde render edilir; roller: success / error / info.
 * Hata toast'ları kullanıcı kapatana kadar kalır; aria-live ile duyurulur.
 */

export type ToastKind = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  kind: ToastKind
  message: string
}

interface ToastState {
  toasts: Toast[]
  toast: (kind: ToastKind, message: string) => void
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  toast: (kind, message) => {
    const id = nextId++
    set((s) => ({ toasts: [...s.toasts, { id, kind, message }] }))
    if (kind !== 'error') {
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
  success: (message: string) => useToastStore.getState().toast('success', message),
  error: (message: string) => useToastStore.getState().toast('error', message),
  info: (message: string) => useToastStore.getState().toast('info', message),
}
