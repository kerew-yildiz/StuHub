import { Link } from 'react-router-dom'

import type { Term } from '../api/terms'
import { formatDate } from '../lib/utils'

interface TermCardProps {
  term: Term
  onDelete: (id: number) => void
  onEdit: (term: Term) => void
}

/** Dönem kartı — ad + tarih aralığı; hover'da hafif yüzey değişimi (stil rehberi). */
export function TermCard({ term, onDelete, onEdit }: TermCardProps) {
  const range =
    term.start_date || term.end_date
      ? `${term.start_date ? formatDate(term.start_date) : '?'} – ${term.end_date ? formatDate(term.end_date) : '?'}`
      : null

  return (
    <article className="glass-panel glass-interactive flex items-center justify-between p-6">
      <Link to={`/donemler/${term.id}`} className="min-w-0">
        <h2 className="text-lg font-semibold">{term.name}</h2>
        {range && <p className="mt-1 text-sm text-stuhub-text-secondary">{range}</p>}
      </Link>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={() => onEdit(term)}
          className="rounded-control px-3 py-1.5 text-sm font-medium text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
          aria-label={`${term.name} dönemini düzenle`}
        >
          Düzenle
        </button>
        <button
          type="button"
          onClick={() => onDelete(term.id)}
          className="rounded-control px-3 py-1.5 text-sm font-medium text-stuhub-error transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10"
          aria-label={`${term.name} dönemini sil`}
        >
          Sil
        </button>
      </div>
    </article>
  )
}
