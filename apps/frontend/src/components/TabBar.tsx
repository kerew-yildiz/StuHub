interface TabBarProps {
  tabs: readonly { id: string; label: string; shortcutHint?: string }[]
  activeId: string
  onSelect: (id: string) => void
  ariaLabel: string
}

/** Yatay sekme çubuğu — cam pill mod değiştirici; mod değişimi rota değil.
 * `shortcutHint` verilirse (örn. "1") etiketin yanında soluk bir tuş rozeti gösterir
 * — klavye kısayolunun keşfedilebilir olması için (2026-09-08 kritik incelemede
 * "Alex/power-user" bulgusu). */
export function TabBar({ tabs, activeId, onSelect, ariaLabel }: TabBarProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="glass-panel-subtle inline-flex max-w-full flex-wrap gap-1 p-1"
    >
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
            className={`rounded-pill px-3.5 py-1.5 text-sm font-medium transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] active:scale-[0.98] ${
              active
                ? 'bg-stuhub-accent-glass border border-stuhub-accent-glass-border text-stuhub-text shadow-sm'
                : 'border border-transparent text-stuhub-text-secondary hover:text-stuhub-text'
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
