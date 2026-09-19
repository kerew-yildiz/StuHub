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

/** Commit eşiği: kartın yüzde 25'i (px) — sürükleme bırakıldığında bu mesafe
 * aşılmışsa kaydırma BAŞARILI, altındaysa kart olduğu yere geri döner. Kart
 * genişliği ölçülemezse (jsdom/test) bu yedek px değeri kullanılır. */
const SWIPE_COMMIT_RATIO = 0.25
const SWIPE_COMMIT_FALLBACK_PX = 90
/** Flick eşiği: hızlı yatay hareket düşük mesafede de commit eder — ama yine
 * kartın en az %10'u kadar sürükleme şart (yanlışlıkla tetiklemesin). */
const SWIPE_FLICK_RATIO = 0.55
const SWIPE_FLICK_MIN_RATIO = 0.1
/** Kart uçuş animasyonu süresi (ms) — hareket token'ından okunur (tek kaynak:
 * theme.css --duration-state; CursorRing ile aynı okuma deseni). Token
 * çözülemezse (jsdom/test) token'ın değeri yedek olarak kullanılır. */
const FLY_MS = (() => {
  if (typeof document === 'undefined') return 200
  const v = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--duration-state'))
  return Number.isFinite(v) ? v : 200
})()

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
 * MASKELEMELİ KAYDIRMA (2026-09-19): kart fade OLMAZ; dış konteyner `overflow-hidden`
 * ile kapalı bir alan oluşturur ve kart bu alanın içine/dışına KAYAR — "kapalı bir
 * alana giriyormuş" hissi. Commit eşiği kartın %25'idir; altında bırakılırsa kart
 * yaylanarak geri döner. Tıkla (veya Space) her seferinde ön↔arka çevirir.
 * Klavye (←/→) erişilebilir alternatif olarak aynı değerlendirme hattını tetikler.
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
  const [snappingBack, setSnappingBack] = useState(false)

  const drag = useRef({ startX: 0, startY: 0, active: false, moved: false, lastX: 0, lastT: 0, vx: 0, width: 0 })
  const cardRef = useRef<HTMLDivElement | null>(null)
  const exitTimer = useRef<number | null>(null)

  // Unmount'ta bekleyen uçuş/geri-dönüş zamanlayıcılarını temizle — yoksa karta
  // ait state güncellemesi unmount sonrası tetiklenir (React uyarısı + leak).
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

  /** Swipe/klavye ile cevap — kart maskeli alandan DIŞARI KAYAR (fade yok). */
  const commit = (direction: SwipeDirection) => {
    if (exiting || exitTimer.current !== null) return
    setSnappingBack(false)
    setExiting(direction)
    exitTimer.current = window.setTimeout(() => {
      exitTimer.current = null
      setExiting(null)
      advance(SWIPE_RATING[direction])
    }, FLY_MS)
  }

  /** Eşik altında bırakma: kart yaylanarak BAŞLANGIÇ konumuna geri döner. */
  const snapBack = () => {
    if (exiting || exitTimer.current !== null) return
    setDragX(0)
    setSnappingBack(true)
    exitTimer.current = window.setTimeout(() => {
      exitTimer.current = null
      setSnappingBack(false)
    }, FLY_MS)
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (exiting) return
    drag.current.width =
      cardRef.current && cardRef.current.offsetWidth > 0
        ? cardRef.current.offsetWidth
        : SWIPE_COMMIT_FALLBACK_PX / SWIPE_COMMIT_RATIO
    // Sıkıntı: setPointerCapture olayları konteynere kilitliyordu; içerideki
    // çevir-butonunun click'i HİÇ tetiklenmiyordu (tıkla-çevir çalışmıyordu).
    // Capture YOK: pointerup aynı elementlerde biter, click normal akar.
    drag.current = { ...drag.current, startX: e.clientX, startY: e.clientY, active: true, moved: false, lastX: e.clientX, lastT: performance.now(), vx: 0 }
    setDragX(0)
    setSnappingBack(false)
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
    const width = Math.max(SWIPE_COMMIT_FALLBACK_PX / SWIPE_COMMIT_RATIO, drag.current.width)
    // Commit eşiği: kartın %25'i — geçilirse kaydırma başarılı.
    const threshold = width * SWIPE_COMMIT_RATIO
    // Eşik VE flick: hızlı yatay hareket (>0.55 px/ms) düşük mesafede de commit eder
    // — ama kartın en az %10'u kadar sürüklenmiş olmalı.
    const flick = Math.abs(drag.current.vx) > SWIPE_FLICK_RATIO && Math.abs(dx) > width * SWIPE_FLICK_MIN_RATIO
    if (dx >= threshold || (flick && drag.current.vx > 0)) commit('right')
    else if (dx <= -threshold || (flick && drag.current.vx < 0)) commit('left')
    else if (dx !== 0) snapBack()
    else setDragX(0)
  }

  const onPointerCancel = () => {
    if (!drag.current.active) return
    drag.current.active = false
    if (dragX !== 0) snapBack()
    else setDragX(0)
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
  // bileşeni transform'da hiç yok), commit'te maskeli alanın DIŞINA kayar, snap-back'te
  // yaylanarak başlangıca döner; aksi halde flip dönüşümü uygulanır.
  let cardTransform: string
  if (exiting === 'right') cardTransform = 'translateX(115%)'
  else if (exiting === 'left') cardTransform = 'translateX(-115%)'
  else if (drag.current.active || dragX !== 0) cardTransform = `translateX(${dragX}px)`
  else cardTransform = flipped ? 'rotateY(180deg)' : 'rotateY(0deg)'

  // Aktif sürükleme sırasında transition YOK (kart parmağı takip eder); uçuş,
  // geri dönüş ve flip animasyonları transition'lı — tek transform transition'ı.
  const transition = exiting || snappingBack
    ? `transform ${FLY_MS}ms var(--ease-out-expo)`
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

      {/* MASKELEME KATMANI (kullanıcı isteği, 2026-09-19): kart fade olmadan bu
          kapalı alanın içine girer / dışına çıkar — overflow-hidden dışarı taşan
          kısmı kırpar, "kapalı bir alana girme" hissi verir. */}
      <div className="mt-5 overflow-hidden rounded-control">
        <div className="relative mx-auto w-full [perspective:1200px]">
          <div
            key={index}
            ref={cardRef}
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
            style={{ transform: cardTransform, transition }}
          >
            {/* Yön damgaları: sürükledikçe belirir — yatay eksende üst-ortada
                (sağ → DOĞRU, sol → YANLIŞ). Konum/kalıp tema.css'te (swipe-stamp). */}
            <span
              aria-hidden="true"
              className="swipe-stamp swipe-stamp--right"
              style={{ opacity: Math.min(1, Math.max(0, dragX / (drag.current.width * SWIPE_COMMIT_RATIO || 90))) }}
            >
              DOĞRU
            </span>
            <span
              aria-hidden="true"
              className="swipe-stamp swipe-stamp--left"
              style={{ opacity: Math.min(1, Math.max(0, -dragX / (drag.current.width * SWIPE_COMMIT_RATIO || 90))) }}
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
