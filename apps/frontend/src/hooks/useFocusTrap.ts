import { useEffect, type RefObject } from 'react'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Modal odak tuzağı (WCAG 2.4.3 — aria-modal="true" diyaloklar için):
 * - Açılışta ilk odaklanabilir elemana odaklanır (autoFocus varsa onu bırakır —
 *   mevcut autoFocus ile uyumlu: trap yalnızca odak diyaloğu terk ederse geri getirir).
 * - Tab/Shift+Tab döngüsünü kap içinde tutar; arka plandaki içeriğe kaçış yok.
 * - Kapanışta odağı açıkken odaklı olan elemana iade eder.
 *
 * `active` false iken hiçbir şey yapmaz — koşullu render'lı diyaloğa uygundur.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
): void {
  useEffect(() => {
    if (!active) return
    const container = containerRef.current
    if (!container) return

    const previouslyFocused = document.activeElement as HTMLElement | null
    const focusables = () =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      )

    // İlk odağı ele al — autoFocus zaten odak verdiyse dokunma.
    if (!container.contains(document.activeElement)) {
      focusables()[0]?.focus()
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return
      const list = focusables()
      if (list.length === 0) return
      const first = list[0]
      const last = list[list.length - 1]
      const current = document.activeElement
      if (event.shiftKey) {
        if (current === first || !container.contains(current)) {
          event.preventDefault()
          last.focus()
        }
      } else if (current === last || !container.contains(current)) {
        event.preventDefault()
        first.focus()
      }
    }

    container.addEventListener('keydown', onKeyDown)
    return () => {
      container.removeEventListener('keydown', onKeyDown)
      // Kapanışta odak iadesi — sayfa geçişlerinde previouslyFocused DOM'da
      // olmayabilir; focus() sessizce no-op olur, hata fırlatmaz.
      previouslyFocused?.focus()
    }
  }, [active, containerRef])
}
