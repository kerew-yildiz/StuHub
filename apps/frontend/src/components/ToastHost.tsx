import { CheckCircle2, Info, X, XCircle } from 'lucide-react'

import { useToastStore, type Toast } from '../stores/toastStore'

/**
 * ToastHost (P3): app kökünde tek instance. Sağ alttan kademeli girer,
 * transform/opacity yalnız; hatalar kapatana kadar kalır. `action` taşıyanlar
 * (ör. "Yeni sürüm hazır → Yenile") da kalıcıdır — kararı kullanıcı verir.
 */

const ICONS: Record<Toast['kind'], typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

function ToastItem({ t }: { t: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss)
  const Icon = ICONS[t.kind]
  return (
    <div
      role={t.kind === 'error' ? 'alert' : 'status'}
      className={`toast toast--${t.kind}`}
    >
      <Icon size={16} aria-hidden="true" />
      <span className="toast__msg">{t.message}</span>
      {t.action && (
        <button
          type="button"
          className="toast__action"
          onClick={() => {
            t.action?.onClick()
            dismiss(t.id)
          }}
        >
          {t.action.label}
        </button>
      )}
      <button
        type="button"
        className="toast__close"
        aria-label="Bildirimi kapat"
        onClick={() => dismiss(t.id)}
      >
        <X size={13} aria-hidden="true" />
      </button>
    </div>
  )
}

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts)
  if (toasts.length === 0) return null
  return (
    <div className="toast-host" aria-live="polite" aria-atomic="false">
      {toasts.map((t) => (
        <ToastItem key={t.id} t={t} />
      ))}
    </div>
  )
}
