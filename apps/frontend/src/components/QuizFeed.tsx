import { ArrowUp, CircleNotch, Confetti, WarningCircle } from '@phosphor-icons/react'
import { useCallback, useEffect, useRef } from 'react'

import { useFeedStore } from '../stores/feedStore'
import { QuizFeedCard } from './QuizFeedCard'

interface QuizFeedProps {
  courseId: number
  chapterId?: number
}

/** Pencereleme yarıçapı: aktif kart + 1 alt + 1 üst mount edilir. */
const WINDOW_RADIUS = 1

/** Sonsuz kaydırma quiz feed'i — dikey tam ekran kartlar, `scroll-snap` ile tek tek durur.
 *
 * Gecikmesizlik iki katmanlı tamponla sağlanır: sunucu havuzu (LLM arka planda) +
 * istemci kuyruğu (`feedStore`, 10'luk parti, 5 altında arka planda yeni parti).
 *
 * Pencereleme: her soru için kaydırma geometrisini bozmayan boş bir `snap` yuvası
 * kalır, ancak yalnızca aktif kart ±1 için kart içeriği mount edilir — DOM birikmez,
 * kaydırma konumu kaymaz (harici sanallaştırma kütüphanesi kullanılmaz). */
export function QuizFeed({ courseId, chapterId }: QuizFeedProps) {
  const queue = useFeedStore((s) => s.queue)
  const index = useFeedStore((s) => s.index)
  const answers = useFeedStore((s) => s.answers)
  const selections = useFeedStore((s) => s.selections)
  const phase = useFeedStore((s) => s.phase)
  const error = useFeedStore((s) => s.error)
  const answerError = useFeedStore((s) => s.answerError)
  const submitting = useFeedStore((s) => s.submitting)
  const generating = useFeedStore((s) => s.generating)
  const mastery = useFeedStore((s) => s.mastery)

  const containerRef = useRef<HTMLDivElement>(null)
  const slotRefs = useRef(new Map<number, HTMLElement>())
  const observerRef = useRef<IntersectionObserver | null>(null)

  const total = queue.length
  /** Kuyruk sonu yuvası — durum kartı (yükleniyor / hazırlanıyor / hata / bitti). */
  const tailIndex = total

  useEffect(() => {
    void useFeedStore.getState().loadInitial(courseId, chapterId ?? null)
    // Bileşen ayrılırken arka planda yoklama bırakma.
    return () => useFeedStore.getState().suspend()
  }, [courseId, chapterId])

  /** Verilen yuvaya kaydırır — TikTok/Reels tarzı hızlı geçiş için tarayıcının varsayılan
   * `smooth` kaydırması (mesafeye göre değişken, genelde 300-500ms) yerine sabit kısa
   * süreli (180ms) elle animasyon kullanılır. `prefers-reduced-motion`: anında atlar.
   *
   * 2026-09-08 canlı bulgu (ekran kaydında yakalandı): `goTo()` store'daki `index`'i
   * güncelledikten HEMEN sonra bu fonksiyonu çağırıyordu — React yeni kartı (WINDOW_RADIUS
   * penceresine yeni giren, henüz hiç mount olmamış bir soru) DOM'a basıp boyamadan
   * kaydırma animasyonu başlıyordu. Sonuç: özellikle hızlı art arda geçişlerde hedef panel
   * bir-iki kare boyunca BOŞ görünüyordu, içerik "geç" beliriyordu. Düzeltme: animasyonun
   * asıl başlangıcı bir `requestAnimationFrame` ile ertelenir — bu, React'in state
   * güncellemesini DOM'a basıp taraycının bir sonraki boyamasını yapması için yeterli. */
  const scrollToSlot = useCallback((slot: number) => {
    const container = containerRef.current
    if (!container) return

    const reduced =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (reduced || typeof requestAnimationFrame !== 'function') {
      const target = slotRefs.current.get(slot)
      if (target) container.scrollTop = target.offsetTop
      return
    }

    requestAnimationFrame(() => {
      // Bir kare beklendi — hedef kart artık mount olmuş/render edilmiş olmalı.
      // `offsetTop` da bu yüzden burada, animasyondan hemen önce ölçülüyor.
      const target = slotRefs.current.get(slot)
      if (!target) return
      const from = container.scrollTop
      const to = target.offsetTop
      const distance = to - from
      const duration = 180
      const start = performance.now()
      // easeOutCubic — hızlı başlar, yumuşak biter (TikTok'un kısa/keskin snap hissi).
      const ease = (t: number) => 1 - (1 - t) ** 3

      // CSS scroll-snap, elle yazılan scrollTop'la "yarışıp" titreşime yol açabilir —
      // animasyon sürerken snap'i geçici kapatıp bitince geri açıyoruz.
      container.style.scrollSnapType = 'none'
      const step = (now: number) => {
        const elapsed = Math.min((now - start) / duration, 1)
        container.scrollTop = from + distance * ease(elapsed)
        if (elapsed < 1) {
          requestAnimationFrame(step)
        } else {
          container.style.scrollSnapType = ''
        }
      }
      requestAnimationFrame(step)
    })
  }, [])

  // Aktif soruyla etkileşime girilmeden (cevap/atla) SIRADAKİ soruya fiziksel kaydırmayı
  // (tekerlek/trackpad/dokunma) engeller — geriye kaydırma serbest. IntersectionObserver'daki
  // "geri al" düzeltmesi (aşağıda) bunun için de bir güvenlik ağı, ama o düzeltme kaydırma
  // ANIMASYONU bittikten SONRA devreye girer (kullanıcı bir an sıradaki soruyu görür); burada
  // olayı `preventDefault` ile en baştan durdurarak o "yanıp sönme" hissini de ortadan kaldırıyoruz.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const canAdvance = () => {
      const { queue, index: current, interacted } = useFeedStore.getState()
      const active = queue[current]
      return !active || Boolean(interacted[active.feed_id])
    }

    /** Olay bir kartın kendi iç kaydırılabilir alanından geliyorsa ve o alan henüz
     * sonuna gelmediyse, dışarıdaki feed'i değil kartın kendi içeriğini kaydırmasına
     * izin verilir (uzun soru metinleri için). */
    const blocksOuterScroll = (target: EventTarget | null): boolean => {
      const el = (target as HTMLElement | null)?.closest('.overflow-y-auto') as HTMLElement | null
      if (!el || el === container) return true
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1
      return atBottom
    }

    const onWheel = (event: WheelEvent) => {
      if (event.deltaY > 0 && !canAdvance() && blocksOuterScroll(event.target)) {
        event.preventDefault()
      }
    }

    let touchStartY = 0
    const onTouchStart = (event: TouchEvent) => {
      touchStartY = event.touches[0]?.clientY ?? 0
    }
    const onTouchMove = (event: TouchEvent) => {
      const currentY = event.touches[0]?.clientY ?? touchStartY
      const swipingUp = touchStartY - currentY > 0 // parmak yukarı = içerik ileri kayar
      if (swipingUp && !canAdvance() && blocksOuterScroll(event.target)) {
        event.preventDefault()
      }
    }

    container.addEventListener('wheel', onWheel, { passive: false })
    container.addEventListener('touchstart', onTouchStart, { passive: true })
    container.addEventListener('touchmove', onTouchMove, { passive: false })
    return () => {
      container.removeEventListener('wheel', onWheel)
      container.removeEventListener('touchstart', onTouchStart)
      container.removeEventListener('touchmove', onTouchMove)
    }
  }, [])

  // Görünür kartı sapta → store index'i → prefetch tetikleyicisi.
  //
  // TEK, kalıcı observer: önceki sürüm bu efekti `[total, ...]`'a bağlıyordu, yani
  // tampon her tamamlandığında (ör. tam da "Atla"/cevap sonrası goTo() ile aynı anda)
  // observer disconnect edilip TÜM yuvalar için YENİDEN kuruluyordu. IntersectionObserver
  // yeni gözlenen (hâlâ görünür) elemanlar için ANINDA senkron olmayan bir "sentetik"
  // callback tetikler — bu, goTo()'nun az önce başlattığı animasyonla aynı ana denk
  // gelip store index'ini beklenmedik bir yuvaya (ör. en son eklenen/kuyruğun sonundaki
  // soru) çekebiliyordu (2026-09-08 canlı bulgu: "Atla" en son üretilen soruya atlıyordu).
  // Düzeltme: observer YALNIZCA bir kez kurulur; yeni yuvalar `registerSlot` ile tek tek
  // gözleme eklenir/çıkarılır, tüm liste asla yeniden gözlemlenmez.
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const root = containerRef.current
    if (!root) return

    const observer = new IntersectionObserver(
      (entries) => {
        let best: { slot: number; ratio: number } | null = null
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const slot = Number((entry.target as HTMLElement).dataset.feedSlot)
          if (Number.isNaN(slot)) continue
          if (!best || entry.intersectionRatio > best.ratio) {
            best = { slot, ratio: entry.intersectionRatio }
          }
        }
        if (best && best.ratio >= 0.5) {
          useFeedStore.getState().setIndex(best.slot)
          const actual = useFeedStore.getState().index
          // Store ileri geçişi reddettiyse (aktif soruyla etkileşime girilmedi) kaydırma
          // fiziksel olarak ilerlemiş olabilir — kullanıcıyı hâlâ aktif olan karta geri al.
          if (actual !== best.slot) scrollToSlot(actual)
        }
      },
      { root, threshold: [0.5, 0.9] },
    )
    observerRef.current = observer
    for (const element of slotRefs.current.values()) observer.observe(element)
    return () => {
      observer.disconnect()
      observerRef.current = null
    }
  }, [scrollToSlot])

  const registerSlot = useCallback((slot: number, element: HTMLElement | null) => {
    const previous = slotRefs.current.get(slot)
    if (previous && previous !== element) observerRef.current?.unobserve(previous)
    if (element) {
      slotRefs.current.set(slot, element)
      observerRef.current?.observe(element)
    } else {
      slotRefs.current.delete(slot)
    }
  }, [])

  const goTo = useCallback(
    (slot: number) => {
      const target = Math.max(0, Math.min(slot, tailIndex))
      useFeedStore.getState().setIndex(target)
      // Etkileşime girilmeden ileri istenirse store isteği reddeder — gerçek indekse dön
      // (kullanıcı etkileşimsiz sıradaki soruyu GÖREMEZ).
      scrollToSlot(useFeedStore.getState().index)
    },
    [tailIndex, scrollToSlot],
  )

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const onButton = (event.target as HTMLElement).tagName === 'BUTTON'
    if (event.key === 'ArrowDown' || event.key === 'PageDown' || (event.key === ' ' && !onButton)) {
      event.preventDefault()
      goTo(index + 1)
    } else if (event.key === 'ArrowUp' || event.key === 'PageUp') {
      event.preventDefault()
      goTo(index - 1)
    }
  }

  const busy = phase === 'loading' || generating

  const showMastery = mastery !== null && mastery.total > 0

  return (
    <>
      {showMastery && mastery && (
        <div className="glass-panel mb-3 p-4">
          <div className="flex items-center justify-between text-xs text-stuhub-text-secondary">
            <span>Ustalık</span>
            <span>%{Math.round(mastery.percent)}</span>
          </div>
          <div
            role="progressbar"
            aria-label="Konu ustalığı"
            aria-valuenow={Math.round(mastery.percent)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="mt-2 h-1.5 w-full overflow-hidden rounded-pill bg-stuhub-border"
          >
            <div
              className="h-full rounded-pill bg-stuhub-accent transition-[width] duration-[var(--duration-state)] ease-[var(--ease-out-expo)]"
              style={{ width: `${Math.max(mastery.percent, 2)}%` }}
            />
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        role="feed"
        aria-label="Soru akışı"
        aria-busy={busy}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        className={`no-scrollbar min-h-[24rem] w-full snap-y snap-mandatory overflow-y-auto overscroll-contain rounded-panel outline-none ${
          showMastery ? 'h-[calc(100dvh-16rem)]' : 'h-[calc(100dvh-12rem)]'
        }`}
      >
      {queue.map((question, slot) => {
        const mounted = Math.abs(slot - index) <= WINDOW_RADIUS
        const isActiveSlot = slot === index
        return (
          <section
            key={question.feed_id}
            ref={(element) => registerSlot(slot, element)}
            data-feed-slot={slot}
            // Komşu (aktif olmayan) kartlar WINDOW_RADIUS için mount edilmiş kalır (pürüzsüz
            // geçiş) ama kaydırma sırasında viewport'a birkaç piksel taşabilirler — `disabled`
            // olmayan Atla/cevap butonları o an tıklanabilir kalıyordu, kullanıcı görmediği bir
            // soruyu yanlışlıkla cevaplıyor/atlıyordu (2026-09-08 canlı bulgu, ekran seçici ile
            // doğrulandı: komşu kartın butonu viewport'un 37px üstünde ama hâlâ `disabled` değildi).
            // `pointer-events-none`: yalnızca aktif kart tıklama alabilir.
            className={`h-full snap-start snap-always py-2 ${isActiveSlot ? '' : 'pointer-events-none'}`}
            aria-label={`Soru ${slot + 1}`}
          >
            {mounted && (
              <QuizFeedCard
                question={question}
                result={answers[question.feed_id] ?? null}
                selectedIndex={selections[question.feed_id] ?? null}
                active={slot === index}
                locked={submitting && slot === index}
                isLast={slot === total - 1}
                answerError={slot === index ? answerError : null}
                onAnswer={(selectedIndex, elapsedMs) =>
                  void useFeedStore.getState().submitAnswer(question.feed_id, selectedIndex, elapsedMs)
                }
                onSkip={() => {
                  void useFeedStore.getState().skipQuestion(question.feed_id)
                  goTo(slot + 1)
                }}
                onNext={() => goTo(slot + 1)}
                onToggleSave={() => void useFeedStore.getState().toggleSave(question.feed_id)}
              />
            )}
          </section>
        )
      })}

      <section
        ref={(element) => registerSlot(tailIndex, element)}
        data-feed-slot={tailIndex}
        className="h-full snap-start snap-always py-2"
        aria-label="Akış durumu"
      >
        {Math.abs(tailIndex - index) <= WINDOW_RADIUS && (
          <div className="glass-panel flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            {phase === 'error' ? (
              <>
                <WarningCircle size={28} className="text-stuhub-error" />
                <p className="text-sm text-stuhub-error" role="alert">
                  {error ?? 'Sorular alınamadı. Bağlantını kontrol et.'}
                </p>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void useFeedStore.getState().retry()}
                >
                  Tekrar dene
                </button>
              </>
            ) : phase === 'loading' ? (
              <>
                <CircleNotch size={28} className="animate-spin text-stuhub-text-secondary" />
                <p className="text-sm text-stuhub-text-secondary" role="status">
                  Sorular yükleniyor…
                </p>
              </>
            ) : phase === 'waiting' || generating ? (
              <>
                <CircleNotch size={28} className="animate-spin text-stuhub-text-secondary" />
                <p className="text-sm text-stuhub-text-secondary" role="status">
                  Yeni sorular hazırlanıyor…
                </p>
                <p className="text-xs text-stuhub-text-muted">
                  Hazır olunca burada görünecek, sayfayı yenilemene gerek yok.
                </p>
              </>
            ) : (
              <>
                <Confetti size={28} className="text-stuhub-accent" />
                <p className="text-sm text-stuhub-text-secondary" role="status">
                  Şimdilik bu kadar. Havuz dolunca yeni sorular gelecek.
                </p>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void useFeedStore.getState().retry()}
                >
                  Yeni soru getir
                </button>
              </>
            )}
            {total > 0 && (
              <button
                type="button"
                onClick={() => goTo(0)}
                className="flex items-center gap-1.5 rounded-pill px-3 py-1.5 text-xs text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
              >
                <ArrowUp size={14} />
                Başa dön
              </button>
            )}
          </div>
        )}
      </section>
      </div>
    </>
  )
}
