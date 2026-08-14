interface TabBarProps {
  tabs: readonly { id: string; label: string }[]
  activeId: string
  onSelect: (id: string) => void
  ariaLabel: string
}

/** Yatay sekme çubuğu — pill mod değiştirici; mod değişimi rota değil (Şema 5). */
export function TabBar({ tabs, activeId, onSelect, ariaLabel }: TabBarProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex max-w-full flex-wrap gap-1 rounded-md border border-stuhub-border bg-stuhub-surface p-1"
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
            className={`rounded-sm px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
              active
                ? 'bg-stuhub-accent/10 text-stuhub-accent'
                : 'text-stuhub-text-secondary hover:bg-stuhub-surface-hover hover:text-stuhub-text'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
