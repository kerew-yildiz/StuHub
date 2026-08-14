interface TabBarProps {
  tabs: readonly { id: string; label: string }[]
  activeId: string
  onSelect: (id: string) => void
  ariaLabel: string
}

/** Yatay sekme çubuğu — mod değişimi rota değil (Quizlet/OmniSets deseni). */
export function TabBar({ tabs, activeId, onSelect, ariaLabel }: TabBarProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex flex-wrap gap-1 border-b border-stuhub-border"
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
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              active
                ? 'border-stuhub-accent text-stuhub-accent'
                : 'border-transparent text-stuhub-text-secondary hover:text-stuhub-text'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
