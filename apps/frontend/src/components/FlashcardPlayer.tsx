import { Confetti } from '@phosphor-icons/react'
import { useState } from 'react'

import { submitReview, type DueCard, type Rating } from '../api/flashcards'
import type { Citation } from '../api/notes'
import { hueColorVar, hueSoftVar, hueTextVar } from '../lib/courseColors'
import { CitationPopup } from './CitationPopup'

interface FlashcardPlayerProps {
  dueCards: DueCard[]
  onFinished: () => void
  onExit: () => void
  /** Ders hue id'si — kart üst şeridi ve konu çipi rengi (Şema 5). */
  hueId?: string
}

/** Atıf çipi için kaynak etiketi (Kitap s.X / Sunum slayt X). */
function citationLabel(citation: Citation): string {
  switch (citation.source_type) {
    case 'textbook':
      return citation.page != null ? `Kitap s.${citation.page}` : 'Kitap'
    case 'slides':
      return citation.slide != null ? `Sunum slayt ${citation.slide}` : 'Sunum'
    default:
      return 'Not'
  }
}

const RATING_LABELS: Record<Rating, string> = {
  again: 'Again',
  hard: 'Hard',
  good: 'Good',
  easy: 'Easy',
}

const RATING_STYLES: Record<Rating, string> = {
  again:
    'rounded-control border border-stuhub-error bg-stuhub-error/10 px-2 py-2 text-sm font-medium text-stuhub-error transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-error/20 active:scale-[0.98]',
  hard: 'rounded-control border border-stuhub-warning bg-stuhub-warning/10 px-2 py-2 text-sm font-medium text-stuhub-warning transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-warning/20 active:scale-[0.98]',
  good: 'rounded-control border border-stuhub-accent-glass-border bg-stuhub-accent-glass px-2 py-2 text-sm font-medium text-stuhub-text transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover active:scale-[0.98]',
  easy: 'rounded-control border border-stuhub-success bg-stuhub-success/10 px-2 py-2 text-sm font-medium text-stuhub-success transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-success/20 active:scale-[0.98]',
}

const RATINGS: Rating[] = ['again', 'hard', 'good', 'easy']

/** Flashcard oynatıcı — ön/arka yüz, SM-2 butonları, ilerleme ve özet (Faz V2.2). */
export function FlashcardPlayer({
  dueCards,
  onFinished,
  onExit,
  hueId,
}: FlashcardPlayerProps) {
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [finished, setFinished] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)

  if (dueCards.length === 0) {
    return (
      <div className="glass-panel p-6 text-center">
        <p className="text-sm text-stuhub-text-secondary">Tekrar bekleyen kart yok.</p>
      </div>
    )
  }

  if (finished) {
    return (
      <div className="glass-panel p-6 text-center">
        <h3 className="flex items-center justify-center gap-2 text-xl font-semibold">
          <Confetti weight="fill" className="h-6 w-6 text-stuhub-warning" aria-hidden="true" />
          Bugünlük tekrar tamamlandı
        </h3>
        <p className="mt-2 text-sm text-stuhub-text-secondary">
          {dueCards.length} kart gözden geçirildi.
        </p>
        <button
          type="button"
          onClick={onFinished}
          className="mt-5 rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
        >
          Kapat
        </button>
      </div>
    )
  }

  const card = dueCards[index]
  const progress = (index / dueCards.length) * 100

  const handleRating = async (rating: Rating) => {
    if (submitting) return
    setSubmitting(true)
    try {
      await submitReview(card.set_id, card.card_index, rating)
    } catch {
      // Tekrar hatası akışı durdurmasın; bir sonraki karta geç.
    } finally {
      setSubmitting(false)
    }
    if (index + 1 >= dueCards.length) {
      setFinished(true)
    } else {
      setIndex((i) => i + 1)
      setFlipped(false)
    }
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex items-center justify-between">
        <span className="text-sm text-stuhub-text-secondary">
          {index + 1} / {dueCards.length}
        </span>
        <button
          type="button"
          onClick={onExit}
          className="rounded-control px-2 py-1 text-sm font-medium text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
        >
          Çık
        </button>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-pill bg-stuhub-border">
        <div
          className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
          style={{ width: `${Math.max(progress, 2)}%` }}
        />
      </div>

      {/* Kart — ön yüz tıklanınca arka yüze çevrilir */}
      <div className="mt-5 [perspective:1200px]">
        <div
          className="relative min-h-72 w-full transition-transform duration-[var(--duration-state)] ease-[var(--ease-out-expo)] [transform-style:preserve-3d]"
          style={{ transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}
        >
          {!flipped ? (
            <button
              type="button"
              onClick={() => setFlipped(true)}
              className="glass-panel-subtle absolute inset-0 flex flex-col items-center justify-center border-t-4 p-6 text-center [backface-visibility:hidden]"
              style={hueId ? { borderTopColor: hueColorVar(hueId) } : undefined}
            >
              <span
                className="rounded-chip px-2 py-0.5 text-xs font-medium"
                style={
                  hueId
                    ? { backgroundColor: hueSoftVar(hueId), color: hueTextVar(hueId) }
                    : undefined
                }
              >
                {card.card.topic}
              </span>
              <p className="mt-4 text-lg font-semibold leading-relaxed">{card.card.front}</p>
              <p className="mt-4 text-xs text-stuhub-text-secondary">Çevirmek için tıkla</p>
            </button>
          ) : (
            <div
              className="glass-panel absolute inset-0 flex flex-col overflow-y-auto border-t-4 p-6 [backface-visibility:hidden] [transform:rotateY(180deg)]"
              style={hueId ? { borderTopColor: hueColorVar(hueId) } : undefined}
            >
              <span
                className="self-start rounded-chip px-2 py-0.5 text-xs font-medium"
                style={
                  hueId
                    ? { backgroundColor: hueSoftVar(hueId), color: hueTextVar(hueId) }
                    : undefined
                }
              >
                {card.card.topic}
              </span>
              <p className="mt-3 text-base leading-relaxed">{card.card.back}</p>

              {card.card.citations.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {card.card.citations.map((citation) => (
                    <button
                      key={citation.id}
                      type="button"
                      onClick={() => setActiveCitation(citation)}
                      className="glass-panel-subtle glass-interactive rounded-chip px-2 py-1 text-xs font-medium text-stuhub-text-secondary"
                    >
                      {citationLabel(citation)}
                    </button>
                  ))}
                </div>
              )}

              <div className="mt-auto grid grid-cols-4 gap-2 pt-4">
                {RATINGS.map((rating) => (
                  <button
                    key={rating}
                    type="button"
                    onClick={() => void handleRating(rating)}
                    disabled={submitting}
                    className={`${RATING_STYLES[rating]} disabled:opacity-50 disabled:active:scale-100`}
                  >
                    {RATING_LABELS[rating]}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {activeCitation && (
        <CitationPopup
          citation={activeCitation}
          onClose={() => setActiveCitation(null)}
          preloadedText={activeCitation.quote}
          sourceLabel={citationLabel(activeCitation)}
        />
      )}
    </div>
  )
}
