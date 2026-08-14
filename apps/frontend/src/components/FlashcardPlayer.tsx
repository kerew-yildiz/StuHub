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
    'rounded-sm border border-stuhub-error bg-stuhub-error/10 px-2 py-2 text-sm font-medium text-stuhub-error transition-colors duration-150 hover:bg-stuhub-error/20',
  hard: 'rounded-sm border border-stuhub-warning bg-stuhub-warning/10 px-2 py-2 text-sm font-medium text-stuhub-warning transition-colors duration-150 hover:bg-stuhub-warning/20',
  good: 'rounded-sm border border-stuhub-accent bg-stuhub-accent/10 px-2 py-2 text-sm font-medium text-stuhub-accent transition-colors duration-150 hover:bg-stuhub-accent/20',
  easy: 'rounded-sm border border-stuhub-success bg-stuhub-success/10 px-2 py-2 text-sm font-medium text-stuhub-success transition-colors duration-150 hover:bg-stuhub-success/20',
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
      <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6 text-center">
        <p className="text-sm text-stuhub-text-secondary">Tekrar bekleyen kart yok.</p>
      </div>
    )
  }

  if (finished) {
    return (
      <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6 text-center">
        <h3 className="text-xl font-semibold">Bugünlük tekrar tamamlandı 🎉</h3>
        <p className="mt-2 text-sm text-stuhub-text-secondary">
          {dueCards.length} kart gözden geçirildi.
        </p>
        <button
          type="button"
          onClick={onFinished}
          className="mt-5 rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
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
    <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-6">
      <div className="flex items-center justify-between">
        <span className="text-sm text-stuhub-text-secondary">
          {index + 1} / {dueCards.length}
        </span>
        <button
          type="button"
          onClick={onExit}
          className="rounded-sm px-2 py-1 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
        >
          Çık
        </button>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stuhub-border">
        <div
          className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
          style={{ width: `${Math.max(progress, 2)}%` }}
        />
      </div>

      {/* Kart — ön yüz tıklanınca arka yüze çevrilir */}
      <div className="mt-5 [perspective:1200px]">
        <div
          className="relative min-h-72 w-full transition-transform duration-200 ease-out [transform-style:preserve-3d]"
          style={{ transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}
        >
          {!flipped ? (
            <button
              type="button"
              onClick={() => setFlipped(true)}
              className="absolute inset-0 flex flex-col items-center justify-center rounded-md border border-t-4 border-stuhub-border bg-stuhub-bg p-6 text-center [backface-visibility:hidden]"
              style={hueId ? { borderTopColor: hueColorVar(hueId) } : undefined}
            >
              <span
                className="rounded-sm px-2 py-0.5 text-xs font-medium"
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
              className="absolute inset-0 flex flex-col overflow-y-auto rounded-md border border-t-4 border-stuhub-border bg-stuhub-bg p-6 [backface-visibility:hidden] [transform:rotateY(180deg)]"
              style={hueId ? { borderTopColor: hueColorVar(hueId) } : undefined}
            >
              <span
                className="self-start rounded-sm px-2 py-0.5 text-xs font-medium"
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
                      className="rounded-sm border border-stuhub-border px-2 py-1 text-xs font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
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
                    className={`${RATING_STYLES[rating]} disabled:opacity-50`}
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
