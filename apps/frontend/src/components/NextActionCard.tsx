import { useEffect, useState } from 'react'

import { fetchNextAction, type NextAction, type NextActionKind } from '../api/nextAction'
import { BookOpen, CheckCircle, Crosshair, Layers, CircleAlert } from 'lucide-react'

export interface NextActionCardProps {
  courseId: number
  /** `action='cards'` tıklanınca `flashcard_sets.id` ile çağrılır — sayfaya bağlama Main'in işi. */
  onOpenCards?: (setId: number) => void
  /** `action='error_quiz'` tıklanınca çağrılır. */
  onOpenErrorQuiz?: () => void
  /** `action='read_chapter'` tıklanınca `chapters.id` ile çağrılır. */
  onOpenChapter?: (chapterId: number) => void
}

const ICON: Record<NextActionKind, typeof Layers> = {
  cards: Layers,
  error_quiz: Crosshair,
  read_chapter: BookOpen,
  none: CheckCircle,
}

const BUTTON_LABEL: Record<Exclude<NextActionKind, 'none'>, string> = {
  cards: 'Kartları tekrarla',
  error_quiz: 'Kurtarma turu başlat',
  read_chapter: 'Bölümü oku',
}

/** Dersin tek karar kartı — "bugün ne çalışsam?" (Plan #13, deterministik, LLM YOK).
 *
 * Tek buton, aksiyona göre ilgili `onOpen*` geri çağrısını tetikler; gerçek sayfa
 * yönlendirmesi bu bileşenin dışında (Main) yapılır. */
export function NextActionCard({
  courseId,
  onOpenCards,
  onOpenErrorQuiz,
  onOpenChapter,
}: NextActionCardProps) {
  const [action, setAction] = useState<NextAction | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setAction(null)
    setError('')
    fetchNextAction(courseId)
      .then((result) => {
        if (!cancelled) setAction(result)
      })
      .catch(() => {
        if (!cancelled) setError('Öneri alınamadı. Lütfen tekrar deneyin.')
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  // Sıkıntı #1: kendi panelini sarmalamaz — zaten bir feature-card içinde render
  // edilir; nested glass-panel (iç içe kart) yasak (yönerge §5).
  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-stuhub-error">
        <CircleAlert size={20} aria-hidden="true" />
        {error}
      </div>
    )
  }

  if (action === null) {
    return (
      <div className="text-sm text-stuhub-text-muted">Öneri hazırlanıyor…</div>
    )
  }

  const Icon = ICON[action.action]

  function handleClick() {
    if (action === null) return
    if (action.action === 'cards' && action.target_id !== null) {
      onOpenCards?.(action.target_id)
    } else if (action.action === 'error_quiz') {
      onOpenErrorQuiz?.()
    } else if (action.action === 'read_chapter' && action.target_id !== null) {
      onOpenChapter?.(action.target_id)
    }
  }

  return (
    <div className="flex flex-1 flex-col items-start justify-center gap-3 self-stretch">
      <div className="flex items-center gap-3">
        <Icon size={24} className="shrink-0 text-stuhub-accent" aria-hidden="true" />
        {/* Kart başlığı feature-card__top'ta zaten var — eyebrow duplikasyonu kaldırıldı;
            satır cart'ın dikey merkezine hizalandı (sıkıntı: bitişik yazılar). */}
        <p className="text-sm text-stuhub-text">{action.reason}</p>
      </div>
      {action.action !== 'none' && (
        <button type="button" className="btn-primary" onClick={handleClick}>
          {BUTTON_LABEL[action.action]}
        </button>
      )}
    </div>
  )
}

export default NextActionCard
