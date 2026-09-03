import { PencilSimple, X } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'

import type { Term } from '../api/terms'
import { formatDate } from '../lib/utils'

interface TermCardProps {
  term: Term
  onDelete: (id: number) => void
  onEdit: (term: Term) => void
}

/** Dönem kartı — tüm bar tıklanabilir/gezinilebilir, ad + tarih aralığı (stil rehberi). */
export function TermCard({ term, onDelete, onEdit }: TermCardProps) {
  const navigate = useNavigate()
  const range =
    term.start_date || term.end_date
      ? `${term.start_date ? formatDate(term.start_date) : '?'} – ${term.end_date ? formatDate(term.end_date) : '?'}`
      : null

  return (
    <article
      role="link"
      tabIndex={0}
      onClick={() => navigate(`/donemler/${term.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/donemler/${term.id}`)
        }
      }}
      className="glass-panel glass-interactive flex cursor-pointer items-center justify-between p-6"
    >
      <div className="min-w-0">
        <h2 className="text-lg font-semibold">{term.name}</h2>
        {range && <p className="mt-1 text-sm text-stuhub-text-secondary">{range}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => onEdit(term)}
          className="rounded-control p-2 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
          title="Düzenle"
          aria-label={`${term.name} dönemini düzenle`}
        >
          <PencilSimple className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => onDelete(term.id)}
          className="rounded-control p-2 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10 hover:text-stuhub-error"
          title="Sil"
          aria-label={`${term.name} dönemini sil`}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </article>
  )
}
