import { clsx, type ClassValue } from 'clsx'

/** Koşullu sınıf birleştirici. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}

/** Tarihi Türkçe yerel biçimde gösterir (örn. "14 Ağustos 2026"). */
export function formatDate(date: string | Date, locale = 'tr-TR'): string {
  const value = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(value)
}
