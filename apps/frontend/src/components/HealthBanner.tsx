import { useHealthPolling } from '../stores/appStore'

/** Backend kapalıyken görünen banner (yol haritası 2.2.4 — 5 sn'de bir yoklama). */
export function HealthBanner() {
  const health = useHealthPolling()

  if (health === 'ok' || health === 'checking') {
    return null
  }

  return (
    <div
      role="alert"
      className="bg-stuhub-error px-6 py-2 text-center text-sm text-stuhub-on-error"
    >
      Backend'e bağlanılamıyor. Uygulamayı kullanmak için sunucuyu başlatın.
    </div>
  )
}
