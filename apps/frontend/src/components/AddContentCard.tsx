import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'

type AddContentCardProps = {
  /** Kart başlığı, ör. "Ders ekle". */
  label: string
  /** Tek cümlelik açıklama. */
  description: string
  /** Tıklama aksiyonu — sayfada zaten var olan ekleme akışı (buton varyantı). */
  onClick?: () => void
  /** Gezinme hedefi verilirse kart `<Link>` olur; sayfadaki mevcut CTA yoluna bağlanır. */
  to?: string
  /** `card`: course/chapter kart geometrisi (3/2, min 180px). `term`: dönem kartı geometrisi. */
  variant?: 'card' | 'term'
}

/** Boş grid'de ve dolu grid'in sonunda gösterilen "içerik ekle" kartı.
 *
 * Yeni bir ekleme akışı açmaz; sayfadaki mevcut akışı (Yeni ders / Yeni dönem /
 * Yeni Chapter formu ya da mevcut CTA bağlantısı) tetikler. `max-w-[420px]` üst
 * sınırı, grid'lerde tek öge kaldığında kartın ekran genişliğine yayılmasını
 * engeller (theme.css'teki auto-fit tek ögeyi tüm genişliğe geriyor).
 */
export function AddContentCard({
  label,
  description,
  onClick,
  to,
  variant = 'card',
}: AddContentCardProps) {
  const className = `glass-panel glass-interactive border-dashed w-full max-w-[420px] text-left ${
    variant === 'term' ? 'flex min-h-[96px] items-center gap-3 p-6' : 'course-card'
  }`

  const content = (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-stuhub-accent-glass text-stuhub-accent">
        <Plus size={18} aria-hidden="true" />
      </span>
      <span className="flex min-w-0 flex-col gap-1">
        <span className="text-base font-medium">{label}</span>
        <span className="text-sm text-stuhub-text-secondary">{description}</span>
      </span>
    </>
  )

  const inner =
    variant === 'term' ? (
      content
    ) : (
      <span className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
        {content}
      </span>
    )

  if (to) {
    return (
      <Link to={to} className={className}>
        {inner}
      </Link>
    )
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {inner}
    </button>
  )
}
