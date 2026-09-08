import { Fragment, useId, useMemo } from 'react'

/** Baloncukta gösterilecek tek terim — sözlük kaydının yalnızca gereken iki alanı. */
export interface TooltipTerm {
  term: string
  definition: string
}

export interface TermTooltipProps {
  /** İçinde terim aranacak düz metin. */
  text: string
  /** Sözlük terimleri; boşsa metin olduğu gibi gösterilir. */
  terms: TooltipTerm[]
  /** Sarmalayan `<span>` için ek sınıflar. */
  className?: string
}

/** Türkçe harfleri de kapsayan kelime sınırı (`\b` yalnızca ASCII'dir). */
const BOUNDARY = '[\\p{L}\\p{N}_]'

interface Segment {
  text: string
  definition: string | null
}

/**
 * Metni terim/düz metin parçalarına böler — saf, deterministik regex eşleşmesi.
 *
 * Uzun terimler önce denenir ki "yığın belleği" gibi çok kelimeli bir terim,
 * "yığın" tarafından parçalanmasın. Eşleşme anahtarı her yerde
 * `toLocaleLowerCase('tr')` — Türkçe İ/ı çiftini doğru katlar.
 */
function splitByTerms(text: string, terms: TooltipTerm[]): Segment[] {
  const definitions = new Map<string, string>()
  for (const entry of terms) {
    const term = entry.term.trim()
    if (!term) continue
    const key = term.toLocaleLowerCase('tr')
    if (!definitions.has(key)) definitions.set(key, entry.definition)
  }
  if (definitions.size === 0 || !text) return [{ text, definition: null }]

  const alternatives = [...definitions.keys()]
    .sort((a, b) => b.length - a.length)
    .map((key) => key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')
  const pattern = new RegExp(`(?<!${BOUNDARY})(?:${alternatives})(?!${BOUNDARY})`, 'giu')

  const segments: Segment[] = []
  let cursor = 0
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0
    const definition = definitions.get(match[0].toLocaleLowerCase('tr'))
    if (definition === undefined) continue
    if (start > cursor) segments.push({ text: text.slice(cursor, start), definition: null })
    segments.push({ text: match[0], definition })
    cursor = start + match[0].length
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), definition: null })
  return segments
}

/**
 * Metindeki sözlük terimlerinin üzerine gelince tanımını baloncukta gösterir (plan #29).
 *
 * Saf bileşen: veri çekmez, yalnızca aldığı `text` + `terms` prop'larıyla çalışır.
 */
export function TermTooltip({ text, terms, className }: TermTooltipProps) {
  const baseId = useId()
  const segments = useMemo(() => splitByTerms(text, terms), [text, terms])

  return (
    <span className={className}>
      {segments.map((segment, index) => {
        if (segment.definition === null) {
          return <Fragment key={`${baseId}-${index}`}>{segment.text}</Fragment>
        }
        const tooltipId = `${baseId}-tip-${index}`
        return (
          <span key={`${baseId}-${index}`} className="group relative inline-block">
            <span
              tabIndex={0}
              aria-describedby={tooltipId}
              className="cursor-help border-b border-dotted border-stuhub-accent outline-none"
            >
              {segment.text}
            </span>
            <span
              id={tooltipId}
              role="tooltip"
              className="glass-panel pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 px-3 py-2 text-left text-xs font-normal normal-case leading-relaxed text-stuhub-text-secondary opacity-0 transition-opacity duration-[var(--duration-micro)] group-hover:opacity-100 group-focus-within:opacity-100"
            >
              {segment.definition || 'Bu terim için not içinde tanım bulunamadı.'}
            </span>
          </span>
        )
      })}
    </span>
  )
}

export default TermTooltip
