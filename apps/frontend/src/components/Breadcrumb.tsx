import { CaretRight } from '@phosphor-icons/react'
import { useNavigate } from 'react-router-dom'

export interface BreadcrumbItem {
  label: string
  /** Yoksa (son öğe) mevcut konum sayılır, tıklanamaz. */
  to?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

/**
 * Hiyerarşi gezinme çubuğu — Dönemler › Dönem › Ders › Chapter.
 *
 * Ara adımlara tıklama `replace: true` ile yapılır (history'ye yeni girdi
 * EKLEMEZ) — kartlara tıklayarak aşağı inmek hâlâ `push` (geri tuşu doğru
 * çalışır: chapter → ders → dönemler), ama breadcrumb'tan ileri-geri
 * zıplamak stack'i şişirip geri tuşunu döngüye sokmaz.
 */
export function Breadcrumb({ items }: BreadcrumbProps) {
  const navigate = useNavigate()

  return (
    <nav aria-label="Konum" className="flex flex-wrap items-center gap-1.5 text-sm">
      {items.map((item, index) => {
        const isLast = index === items.length - 1
        return (
          <span key={`${item.label}-${index}`} className="flex items-center gap-1.5">
            {index > 0 && (
              <CaretRight
                className="h-3.5 w-3.5 shrink-0 text-stuhub-text-muted"
                aria-hidden="true"
              />
            )}
            {isLast || !item.to ? (
              <span
                className={isLast ? 'font-medium text-stuhub-text' : 'text-stuhub-text-secondary'}
                aria-current={isLast ? 'page' : undefined}
              >
                {item.label}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => navigate(item.to!, { replace: true })}
                className="rounded-control px-1 -mx-1 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
              >
                {item.label}
              </button>
            )}
          </span>
        )
      })}
    </nav>
  )
}
