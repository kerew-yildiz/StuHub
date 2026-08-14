/**
 * Ders renk paleti (Şema 5 — "Renkli Not Defteri").
 *
 * Renk DEĞERLERİ `styles/theme.css` içindeki `--stuhub-hue-*` token'larında
 * yaşar (tek otorite: YETENEKLER/07-stil-rehberi.md). Bu modül yalnızca
 * paletin yapısını, adlarını ve bir derse renk atama kuralını tanımlar.
 * Bileşenler renk değerini `hueColorVar()` yardımcılarıyla CSS değişkeni
 * olarak kullanır — bileşenlere hex yazılmaz.
 */

export interface CourseHue {
  /** Token soneki: `--stuhub-hue-<id>` / `-text` / `-soft`. */
  id: string
  /** Türkçe görünen ad (form seçicisinde). */
  name: string
}

export const COURSE_HUES: readonly CourseHue[] = [
  { id: 'indigo', name: 'Çivit' },
  { id: 'pine', name: 'Çam' },
  { id: 'burgundy', name: 'Bordo' },
  { id: 'amber', name: 'Amber' },
  { id: 'teal', name: 'Turkuaz' },
  { id: 'plum', name: 'Erik' },
] as const

export type CourseHueId = (typeof COURSE_HUES)[number]['id']

export const FALLBACK_HUE: CourseHue = COURSE_HUES[0]

/** Bilinmeyen/geçersiz hue id'si için fallback'a düşer. */
export function hueById(id: unknown): CourseHue {
  return COURSE_HUES.find((h) => h.id === id) ?? FALLBACK_HUE
}

/** Dersin hue'sunu döndürür: metadata'daki seçim, yoksa id'den kararlı atama. */
export function getCourseHue(course: {
  id: number
  metadata_json?: Record<string, unknown> | null
}): CourseHue {
  const chosen = course.metadata_json?.hue
  if (typeof chosen === 'string' && COURSE_HUES.some((h) => h.id === chosen)) {
    return hueById(chosen)
  }
  return COURSE_HUES[course.id % COURSE_HUES.length]
}

/** `var(--stuhub-hue-<id>)` — nokta/şerit/kenarlık rengi. */
export function hueColorVar(id: string): string {
  return `var(--stuhub-hue-${hueById(id).id})`
}

/** `var(--stuhub-hue-<id>-text)` — WCAG AA güvenli metin rengi. */
export function hueTextVar(id: string): string {
  return `var(--stuhub-hue-${hueById(id).id}-text)`
}

/** `var(--stuhub-hue-<id>-soft)` — yüzey üstü yumuşak zemin rengi. */
export function hueSoftVar(id: string): string {
  return `var(--stuhub-hue-${hueById(id).id}-soft)`
}
