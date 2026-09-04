import { useEffect } from 'react'

import { useConfirmStore } from '../stores/confirmStore'

/**
 * Tema uyumlu onay diyaloğu — `window.confirm()` yerine. `confirmStore`'daki
 * `open`/`message` durumuna göre render edilir; App kökünde bir kez mount edilir.
 */
export function ConfirmDialog() {
  const open = useConfirmStore((s) => s.open)
  const message = useConfirmStore((s) => s.message)
  const respond = useConfirmStore((s) => s.respond)

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') respond(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, respond])

  if (!open) return null

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={() => respond(false)}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-message"
        className="glass-panel w-full max-w-sm p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <p id="confirm-dialog-message" className="text-sm leading-relaxed text-stuhub-text">
          {message}
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={() => respond(false)}
            className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
          >
            İptal
          </button>
          <button
            type="button"
            autoFocus
            onClick={() => respond(true)}
            className="btn-primary"
          >
            Onayla
          </button>
        </div>
      </div>
    </div>
  )
}
