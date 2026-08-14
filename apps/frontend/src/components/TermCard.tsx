import { formatDate } from '../lib/utils'
import type { Term } from '../api/terms'

interface TermCardProps {
  term: Term
  onDelete: (id: number) => void
}

/** Dönem kartı — ad + tarih aralığı; hover'da hafif yüzey değişimi (stil rehberi). */
export function TermCard({ term, onDelete }: TermCardProps) {
  const range =
    term.start_date || term.end_date
      ? `${term.start_date ? formatDate(term.start_date) : '?'} – ${term.end_date ? formatDate(term.end_date) : '?'}`
      : null

  return (
    <article className="flex items-center justify-between rounded-md border border-stuhub-border bg-stuhub-surface p-6 transition-colors duration-150 hover:bg-stuhub-surface-hover">
      <div>
        <h2 className="text-lg font-semibold">{term.name}</h2>
        {range && (
          <p className="mt-1 text-sm text-stuhub-text-secondary">{range}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDelete(term.id)}
        className="rounded-sm px-3 py-1.5 text-sm font-medium text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
        aria-label={`${term.name} dönemini sil`}
      >
        Sil
      </button>
    </article>
  )
}
