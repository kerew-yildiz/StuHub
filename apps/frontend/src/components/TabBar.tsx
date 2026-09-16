import { useLayoutEffect, useRef, useState } from 'react'

interface TabBarProps {
  tabs: readonly { id: string; label: string; shortcutHint?: string }[]
  activeId: string
  onSelect: (id: string) => void
  ariaLabel: string
}

/** Yatay sekme çubuğu — cam pill mod değiştirici; mod değişimi rota değil.
 * `shortcutHint` verilirse (örn. "1") etiketin yanında soluk bir tuş rozeti gösterir
 * — klavye kısayolunun keşfedilebilir olması için (2026-09-08 kritik incelemede
 * "Alex/power-user" bulgusu).
 *
 * Motion (Visual Excellence P2): aktif pill ayrı bir highlight katmanı —
 * sekme değişince ölçülen geometriye kayar (layout morph). Tek element
 * animasyonlu (transform/opacity), wrap ve resize güvenli; prefers-reduced-motion
 * global kural geçişleri 1ms'e indirir. */
export function TabBar({ tabs, activeId, onSelect, ariaLabel }: TabBarProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const [hl, setHl] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  useLayoutEffect(() => {
    const list = listRef.current
    if (!list) return
    const measure = () => {
      const idx = tabs.findIndex((t) => t.id === activeId)
      const btn = list.querySelectorAll<HTMLButtonElement>('[role="tab"]')[idx]
      if (!btn) return
      setHl({ x: btn.offsetLeft, y: btn.offsetTop, w: btn.offsetWidth, h: btn.offsetHeight })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(list)
    return () => ro.disconnect()
  }, [tabs, activeId])

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={ariaLabel}
      className="glass-panel-subtle relative inline-flex max-w-full flex-wrap gap-1 p-1"
    >
      {/* Kayan highlight — button'ların altında, pointer-events none */}
      {hl && (
        <span
          aria-hidden="true"
          className="tabbar-highlight"
          style={{
            width: hl.w,
            height: hl.h,
            transform: `translate(${hl.x}px, ${hl.y}px)`,
          }}
        />
      )}
      {tabs.map((tab) => {
        const active = tab.id === activeId
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(tab.id)}
            title={tab.shortcutHint ? `Kısayol: ${tab.shortcutHint}` : undefined}
            className={`relative rounded-pill px-3.5 py-1.5 text-sm font-medium transition-colors duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] active:scale-[0.98] ${
              active
                ? 'text-stuhub-text'
                : 'text-stuhub-text-secondary hover:text-stuhub-text'
            }`}
          >
            {tab.label}
            {tab.shortcutHint && (
              <span className="ml-1.5 text-xs text-stuhub-text-muted" aria-hidden="true">
                {tab.shortcutHint}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
