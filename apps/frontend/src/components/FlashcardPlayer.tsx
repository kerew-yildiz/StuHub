import { useEffect, useRef, useState } from 'react'

import { submitReview, type DueCard, type Rating } from '../api/flashcards'
import type { Citation } from '../api/notes'
import { CitationPopup } from './CitationPopup'
import { PartyPopper } from 'lucide-react'

interface FlashcardPlayerProps {
  dueCards: DueCard[]
  onFinished: () => void
  onExit: () => void
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

/** Swipe eşiği (px) — bu kadar YATAY sürükleme cevap sayılır. */
const SWIPE_THRESHOLD = 90
/** Kart uçuş animasyonu süresi (ms). */
const FLY_MS = 180

type SwipeDirection = 'left' | 'right'

/** Sağa kaydır = doğru (good), sola kaydır = yanlış/boş (again). */
const SWIPE_RATING: Record<SwipeDirection, Rating> = {
  right: 'good',
  left: 'again',
}

/**
 * Flashcard oynatıcı — ön/arka yüz (serbest çevirme), YATAY swipe değerlendirme,
 * ilerleme ve özet (Faz V2.2 + §42 swipe etkileşimi).
 *
 * Birincil etkileşim swipe'dir: sağa kaydır → doğru, sola kaydır → yanlış.
 * Kart sürüklenirken EĞİLMEZ (tilt/rotate yok): düz yatay kayma + fade. Tıkla
 * (veya Space) her seferinde ön↔arka çevirir. Klavye (←/→) erişilebilir
 * alternatif olarak aynı değerlendirme hattını tetikler.
 */
export function FlashcardPlayer({
  dueCards,
  onFinished,
  onExit,
}: FlashcardPlayerProps) {
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [finished, setFinished] = useState(false)
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null)
  const [dragX, setDragX] = useState(0)
  const [exiting, setExiting] = useState<SwipeDirection | null>(null)

  const drag = useRef({ startX: 0, startY: 0, active: false, moved: false, lastX: 0, lastT: 0, vx: 0 })
  const exitTimer = useRef<number | null>(null)

  // Unmount'ta bekleyen uçuş zamanlayıcısını temizle — yoksa karta ait
  // handleRating state güncellemesi unmount sonrası tetiklenir (React uyarısı + leak).
  useEffect(() => {
    return () => {
      if (exitTimer.current !== null) {
        window.clearTimeout(exitTimer.current)
        exitTimer.current = null
      }
    }
  }, [])

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
          <PartyPopper className="h-6 w-6 text-stuhub-warning" aria-hidden="true" />
          Bugünlük tekrar tamamlandı
        </h3>
        <p className="mt-2 text-sm text-stuhub-text-secondary">
          {dueCards.length} kart gözden geçirildi.
        </p>
        <button
          type="button"
          onClick={onFinished}
          className="btn-primary mt-5"
        >
          Kapat
        </button>
      </div>
    )
  }

  const card = dueCards[index]
  const progress = (index / dueCards.length) * 100

  /** Sonraki karta geç; tekrarı arka planda gönder (hata/yavaş ağ akışı durdurmaz). */
  const advance = (rating: Rating) => {
    void submitReview(card.set_id, card.card_index, rating).catch(() => undefined)
    if (index + 1 >= dueCards.length) {
      setFinished(true)
    } else {
      setIndex((i) => i + 1)
      setFlipped(false)
    }
  }

  /** Swipe/klavye ile cevap — düz yatay uçuş + fade sonrası sonraki karta geçilir. */
  const commit = (direction: SwipeDirection) => {
    if (exiting || exitTimer.current !== null) return
    setExiting(direction)
    setDragX(0)
    exitTimer.current = window.setTimeout(() => {
      exitTimer.current = null
      setExiting(null)
      advance(SWIPE_RATING[direction])
    }, FLY_MS)
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (exiting) return
    // Sıkıntı: setPointerCapture olayları konteynere kilitliyordu; içerideki
    // çevir-butonunun click'i HİÇ tetiklenmiyordu (tıkla-çevir çalışmıyordu).
    // Capture YOK: pointerup aynı elementlerde biter, click normal akar.
    drag.current = { startX: e.clientX, startY: e.clientY, active: true, moved: false, lastX: e.clientX, lastT: performance.now(), vx: 0 }
    setDragX(0)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current.active) return
    const now = performance.now()
    const dt = Math.max(1, now - drag.current.lastT)
    // Hız örnekleme (flick detection): son harekeden px/ms — yumuşatılmış.
    const instV = (e.clientX - drag.current.lastX) / dt
    drag.current.vx = drag.current.vx * 0.7 + instV * 0.3
    drag.current.lastX = e.clientX
    drag.current.lastT = now
    const dx = e.clientX - drag.current.startX
    const dy = e.clientY - drag.current.startY
    // Herhangi bir eksende 8px'i geçen hareket sürüklemedir — bırakınca çevirmesin.
    if (Math.abs(dx) > 8 || Math.abs(dy) > 8) drag.current.moved = true
    // Yalnız YATAY baskın: dikey hareket (sayfa scroll'u) kartı oynatmaz.
    if (Math.abs(dx) >= Math.abs(dy)) setDragX(dx)
  }

  const onPointerUp = (e: React.PointerEvent) => {
    if (!drag.current.active) return
    drag.current.active = false
    const dx = e.clientX - drag.current.startX
    setDragX(0)
    // Eşik VE flick: hızlı yatay hareket (>0.55 px/ms) düşük mesafede de commit eder.
    // Min 24px, yanlışlıkla tetiklemesin.
    const flick = Math.abs(drag.current.vx) > 0.55 && Math.abs(dx) > 24
    if (dx >= SWIPE_THRESHOLD || (flick && drag.current.vx > 0)) commit('right')
    else if (dx <= -SWIPE_THRESHOLD || (flick && drag.current.vx < 0)) commit('left')
  }

  const onPointerCancel = () => {
    drag.current.active = false
    setDragX(0)
  }

  /** Tıkla-çevir: her tıklamada ön↔arka serbest geçiş. Sürükleme sonrası click yutulur. */
  const onCardClick = () => {
    if (drag.current.moved) {
      drag.current.moved = false
      return
    }
    setFlipped((v) => !v)
  }

  // Kart transformu: sürüklenirken parmağı YATAY takip eder (eğim/tilt YOK — rotate
  // bileşeni transform'da hiç yok), bırakınca düz yatay uçuş + fade yapar, aksi
  // halde flip dönüşümü uygulanır.
  let cardTransform: string
  if (exiting === 'right') cardTransform = 'translateX(140%)'
  else if (exiting === 'left') cardTransform = 'translateX(-140%)'
  else if (drag.current.active || dragX !== 0) cardTransform = `translateX(${dragX}px)`
  else cardTransform = flipped ? 'rotateY(180deg)' : 'rotateY(0deg)'

  // Aktif sürükleme sırasında transition YOK (kart parmağı takip eder); bırakınca
  // uçuş (transform + fade) ve flip animasyonları transition'lı — tek transform
  // transition'ı (çift tanım sonuncunun kazanmasıyla süreyi sessizce eziyordu).
  const transition = exiting
    ? `transform ${FLY_MS}ms var(--ease-out-expo), opacity ${FLY_MS}ms var(--ease-out-expo)`
    : dragX === 0
      ? 'transform var(--duration-state) var(--ease-out-expo)'
      : 'none'

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

      {/* Kart — tıkla çevir (serbest ön↔arka), sağa/sola kaydırarak değerlendir */}
      <div className="mt-5 [perspective:1200px]">
        <div
          key={index}
          role="group"
          aria-label="Flashcard — çevirmek için tıkla veya Space; sağa kaydır: doğru, sola kaydır: yanlış. Klavye: sağ ok / sol ok."
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') {
              e.preventDefault()
              commit('right')
            } else if (e.key === 'ArrowLeft') {
              e.preventDefault()
              commit('left')
            } else if (e.key === ' ') {
              // Space = çevir (kullanıcı isteği). Buton/bağlantı odaktayken sayfayı
              // kaydırmasın ve çift tetiklemesin diye hedef kontrolü yapılmaz —
              // konteyner odaktaysa çevirir.
              e.preventDefault()
              setFlipped((v) => !v)
            }
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerCancel}
          className="relative min-h-72 w-full touch-pan-y select-none [transform-style:preserve-3d]"
          style={{ transform: cardTransform, transition, opacity: exiting ? 0 : 1 }}
        >
          {/* Yön damgaları: sürükledikçe belirir — yatay eksende üst-ortada
              (sağ → DOĞRU, sol → YANLIŞ). Konum/kalıp tema.css'te (swipe-stamp). */}
          <span
            aria-hidden="true"
            className="swipe-stamp swipe-stamp--right"
            style={{ opacity: Math.min(1, Math.max(0, dragX / SWIPE_THRESHOLD)) }}
          >
            DOĞRU
          </span>
          <span
            aria-hidden="true"
            className="swipe-stamp swipe-stamp--left"
            style={{ opacity: Math.min(1, Math.max(0, -dragX / SWIPE_THRESHOLD)) }}
          >
            YANLIŞ
          </span>
          {!flipped ? (
            <button
              type="button"
              onClick={onCardClick}
              className="glass-panel-subtle absolute inset-0 flex flex-col items-center justify-center p-6 text-center [backface-visibility:hidden]"
            >
              <span className="glass-panel-subtle rounded-chip px-2 py-0.5 text-xs font-medium text-stuhub-text-secondary">
                {card.card.topic}
              </span>
              <p className="mt-4 text-lg font-semibold leading-relaxed">{card.card.front}</p>
              <p className="mt-4 text-xs text-stuhub-text-secondary">Çevirmek için tıkla</p>
            </button>
          ) : (
            <div
              onClick={onCardClick}
              className="glass-panel no-scrollbar absolute inset-0 flex cursor-pointer flex-col overflow-y-auto p-6 [backface-visibility:hidden] [transform:rotateY(180deg)]"
            >
              <span className="glass-panel-subtle self-start rounded-chip px-2 py-0.5 text-xs font-medium text-stuhub-text-secondary">
                {card.card.topic}
              </span>
              <p className="mt-3 text-base leading-relaxed">{card.card.back}</p>

              {card.card.citations.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {card.card.citations.map((citation) => (
                    <button
                      key={citation.id}
                      type="button"
                      onClick={(e) => {
                        // Çevirmeyi tetiklemesin — yalnız atıf popup'ı açılır.
                        e.stopPropagation()
                        setActiveCitation(citation)
                      }}
                      className="glass-panel-subtle glass-interactive rounded-chip px-2 py-1 text-xs font-medium text-stuhub-text-secondary"
                    >
                      {citationLabel(citation)}
                    </button>
                  ))}
                </div>
              )}

              {/* Serbest çevirme ipucu — arka yüzden ön yüze dönüş de tıklamayla. */}
              <p className="mt-4 text-xs text-stuhub-text-secondary">Çevirmek için tıkla</p>

              <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs">
                <span className="rounded-chip bg-stuhub-error/10 px-2.5 py-1 font-medium text-stuhub-error">
                  ← Sola kaydır: Yanlış
                </span>
                <span className="rounded-chip bg-stuhub-success/10 px-2.5 py-1 font-medium text-stuhub-success">
                  Sağa kaydır: Doğru →
                </span>
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
