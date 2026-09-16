import { useEffect, useRef } from 'react'

import { useAlertStore } from '../stores/alertStore'
import { useFocusTrap } from '../hooks/useFocusTrap'
import { Info } from 'lucide-react'

/**
 * Tema uyumlu tek-butonlu bilgi diyaloğu — `window.alert()` yerine.
 * `alertStore`'daki `open`/`message` durumuna göre render edilir; App kökünde
 * bir kez mount edilir. `ConfirmDialog.tsx` ile aynı görsel dil.
 */
export function AlertDialog() {
  const open = useAlertStore((s) => s.open)
  const message = useAlertStore((s) => s.message)
  const respond = useAlertStore((s) => s.respond)
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(dialogRef, open)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' || event.key === 'Enter') respond()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, respond])

  if (!open) return null

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={() => respond()}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="alert-dialog-message"
        className="glass-panel w-full max-w-sm p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <Info size={20} className="mt-0.5 shrink-0 text-stuhub-accent" aria-hidden="true" />
          <p id="alert-dialog-message" className="text-sm leading-relaxed text-stuhub-text">
            {message}
          </p>
        </div>
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            autoFocus
            onClick={() => respond()}
            className="btn-primary"
          >
            Tamam
          </button>
        </div>
      </div>
    </div>
  )
}
