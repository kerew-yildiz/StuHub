/**
 * Merkezi tarih/sayı biçimlendirme (P2 — Visual Excellence).
 *
 * Uygulama dili Türkçe; tüm kullanıcıya dönük biçimler buradan geçer.
 * Saatler 12:00'a sabitlenir (MonthCalendar pad'indeki DST/classic bug'ı —
 * yerel yarı gece tarihlerinin bir gün geri kaymasını önler).
 */

const TR = 'tr-TR'

export function formatDate(value: string | number | Date, opts?: Intl.DateTimeFormatOptions): string {
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString(TR, opts)
}

/** "12 Mart 2026" — tam tarih */
export function formatDateLong(value: string | number | Date): string {
  return formatDate(value, { day: 'numeric', month: 'long', year: 'numeric' })
}

/** "12 Mar" — kompakt, liste/satır içi */
export function formatDateShort(value: string | number | Date): string {
  return formatDate(value, { day: 'numeric', month: 'short' })
}

/** "12 Mar 2026, Pzt 14:05" — timestamp */
export function formatDateTime(value: string | number | Date): string {
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString(TR, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** Date-only string ("2026-03-12") için güvenli Date — yerel 12:00 (DST-pad). */
export function parseDateOnly(value: string): Date {
  return new Date(`${value}T12:00:00`)
}

export function formatNumber(value: number, opts?: Intl.NumberFormatOptions): string {
  return value.toLocaleString(TR, opts)
}

/** Çalışma dakikasını insan okur biçime çevirir: "1 sa 25 dk" / "45 dk". */
export function formatMinutes(minutes: number): string {
  const m = Math.max(0, Math.round(minutes))
  const h = Math.floor(m / 60)
  const rest = m % 60
  if (h === 0) return `${rest} dk`
  if (rest === 0) return `${h} sa`
  return `${h} sa ${rest} dk`
}
