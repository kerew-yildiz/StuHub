import { ArrowDown, CheckCircle, CircleNotch, Quotes, SkipForward, XCircle } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'

import type { AnswerResult, FeedDifficulty, FeedQuestion } from '../api/feed'
import type { Citation } from '../api/notes'

interface QuizFeedCardProps {
  question: FeedQuestion
  /** Sunucudan gelen değerlendirme; cevaplanmadan önce `null` — doğru cevap DOM'a girmez. */
  result: AnswerResult | null
  /** Kullanıcının seçtiği şık (store'da tutulur — pencereleme kartı unmount edince kaybolmaz). */
  selectedIndex: number | null
  /** Bu kart aktif kart mı (süre ölçümü burada başlar). */
  active: boolean
  /** Cevap gönderimi sürüyor — kart kilitli. */
  locked: boolean
  /** Kuyruğun son sorusu mu (ipucu metni değişir). */
  isLast: boolean
  answerError: string | null
  onAnswer: (selectedIndex: number, elapsedMs: number) => void
  onSkip: () => void
  onNext: () => void
}

const DIFFICULTY_LABEL: Record<FeedDifficulty, string> = {
  easy: 'Kolay',
  medium: 'Orta',
  hard: 'Zor',
}

/** Atıf çipi metni — sayfa/slayt/web başlığı; hiçbiri yoksa alıntının kendisi. */
function citationLabel(citation: Citation): string {
  if (citation.page !== null) return `sayfa ${citation.page}`
  if (citation.slide !== null) return `slayt ${citation.slide}`
  if (citation.title) return citation.title
  if (citation.url) return citation.url
  return citation.quote.slice(0, 40) || 'kaynak'
}

/** Feed'in tek soru kartı — tam yükseklik, dikey kaydırmada bir "ekran".
 *
 * Cevap gönderilene kadar doğru cevap bilgisi hiç render edilmez: `result`
 * yalnızca `POST /feed/{id}/answer` yanıtından gelir. */
export function QuizFeedCard({
  question,
  result,
  selectedIndex,
  active,
  locked,
  isLast,
  answerError,
  onAnswer,
  onSkip,
  onNext,
}: QuizFeedCardProps) {
  const startedAtRef = useRef<number>(Date.now())

  // Süre ölçümü kart aktif olduğunda başlar (kaydırmada önden mount edilen kartlar sayılmaz).
  useEffect(() => {
    if (active && !result) startedAtRef.current = Date.now()
  }, [active, result, question.feed_id])

  const handleSelect = (index: number) => {
    if (result || locked) return
    onAnswer(index, Date.now() - startedAtRef.current)
  }

  return (
    <div className="glass-panel flex h-full flex-col gap-4 overflow-y-auto p-6">
      {(question.topic || question.difficulty) && (
        <div className="flex items-center justify-between gap-2 text-xs text-stuhub-text-secondary">
          {question.topic ? (
            <span className="glass-panel-subtle rounded-pill px-2.5 py-1">{question.topic}</span>
          ) : (
            <span />
          )}
          {question.difficulty && (
            <span className="glass-panel-subtle rounded-pill px-2.5 py-1">
              {DIFFICULTY_LABEL[question.difficulty]}
            </span>
          )}
        </div>
      )}

      <p className="text-lg font-medium leading-relaxed">{question.question}</p>

      <div className="space-y-2">
        {question.options.map((option, index) => {
          let className =
            'glass-panel-subtle w-full rounded-control border border-stuhub-border px-4 py-3 text-left text-sm'
          if (!result) {
            className += ' glass-interactive'
          } else if (index === result.correct_index) {
            className += ' border-stuhub-success bg-stuhub-success/10 text-stuhub-success'
          } else if (index === selectedIndex) {
            className += ' border-stuhub-error bg-stuhub-error/10 text-stuhub-error'
          } else {
            className += ' opacity-60'
          }
          return (
            <button
              key={index}
              type="button"
              onClick={() => handleSelect(index)}
              disabled={result !== null || locked}
              className={className}
            >
              {option}
            </button>
          )
        })}
      </div>

      {locked && !result && (
        <p className="flex items-center gap-2 text-sm text-stuhub-text-secondary" role="status">
          <CircleNotch size={16} className="animate-spin" />
          Cevabın değerlendiriliyor…
        </p>
      )}

      {answerError && !result && (
        <p className="text-sm text-stuhub-error" role="alert">
          {answerError}
        </p>
      )}

      {result && (
        <div
          className={`rounded-control px-4 py-3 text-sm leading-relaxed ${
            result.correct
              ? 'bg-stuhub-success/10 text-stuhub-success'
              : 'bg-stuhub-error/10 text-stuhub-error'
          }`}
          role="status"
        >
          <p className="flex items-center gap-2 font-medium">
            {result.correct ? <CheckCircle size={18} /> : <XCircle size={18} />}
            {result.correct ? 'Doğru!' : 'Yanlış'}
          </p>
          {result.explanation && (
            <p className="mt-1 text-stuhub-text-secondary">{result.explanation}</p>
          )}
          {result.citations && result.citations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {result.citations.map((citation, index) => (
                <span
                  key={`${citation.id}-${index}`}
                  className="glass-panel-subtle flex items-center gap-1 rounded-pill px-2.5 py-1 text-xs text-stuhub-text-secondary"
                >
                  <Quotes size={12} />
                  {citationLabel(citation)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 pt-2">
        {result ? (
          <>
            <span className="flex items-center gap-1.5 text-xs text-stuhub-text-muted">
              <ArrowDown size={14} />
              {isLast ? 'Yeni sorular için kaydır' : 'Sonraki soru için kaydır'}
            </span>
            <button type="button" onClick={onNext} className="btn-primary" disabled={locked}>
              Sonraki
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={onSkip}
            disabled={locked}
            className="flex items-center gap-1.5 rounded-pill px-3 py-1.5 text-xs text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text disabled:opacity-50"
          >
            <SkipForward size={14} />
            Atla
          </button>
        )}
      </div>
    </div>
  )
}
