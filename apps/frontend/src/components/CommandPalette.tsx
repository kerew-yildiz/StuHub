import { MagnifyingGlass } from '@phosphor-icons/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import { usePaletteStore } from '../stores/paletteStore'

interface PaletteItem {
  id: string
  label: string
  sublabel?: string
  to: string
}

/**
 * Global komut paletiyle gezinme — Ctrl/Cmd+K açar, ok tuşları + Enter seçer, Esc
 * kapatır. Herhangi bir dönem/derse iki tuşla ulaşmayı sağlar (2026-09-08 kritik
 * incelemede "Alex/power-user" bulgusu: tek yol sidebar'da tıklayarak açmaktı, çok
 * sayıda ders/dönemi olan bir öğrenci için yavaştı).
 */
export function CommandPalette() {
  const open = usePaletteStore((s) => s.open)
  const toggle = usePaletteStore((s) => s.toggle)
  const close = usePaletteStore((s) => s.close)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const [terms, setTerms] = useState<Term[]>([])
  const [coursesByTerm, setCoursesByTerm] = useState<Record<number, Course[]>>({})
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Ctrl/Cmd+K her yerden paleti açar/kapatır — metin girişindeyken bile (arama
  // amacıyla açılan bir palet için bu istisna doğru: Slack, Linear, Notion hepsi
  // aynısını yapar).
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        toggle()
      } else if (event.key === 'Escape' && open) {
        close()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, toggle, close])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setSelected(0)
    requestAnimationFrame(() => inputRef.current?.focus())
    termsApi
      .list()
      .then(async (list) => {
        setTerms(list)
        const entries = await Promise.all(
          list.map(async (term) => [term.id, await coursesApi.listByTerm(term.id).catch(() => [])] as const),
        )
        setCoursesByTerm(Object.fromEntries(entries))
      })
      .catch(() => {
        // Palet listesi alınamazsa statik öğelerle (Dönemler/Ayarlar) çalışmaya devam eder.
      })
  }, [open])

  const items = useMemo((): PaletteItem[] => {
    const staticItems: PaletteItem[] = [
      { id: 'home', label: 'Dönemler', to: '/' },
      { id: 'settings', label: 'Ayarlar', to: '/ayarlar' },
    ]
    const termItems: PaletteItem[] = terms.map((term) => ({
      id: `term-${term.id}`,
      label: term.name,
      sublabel: 'Dönem',
      to: `/donemler/${term.id}`,
    }))
    const courseItems: PaletteItem[] = terms.flatMap((term) =>
      (coursesByTerm[term.id] ?? []).map((course) => ({
        id: `course-${course.id}`,
        label: course.name,
        sublabel: term.name,
        to: `/dersler/${course.id}`,
      })),
    )
    const all = [...staticItems, ...termItems, ...courseItems]
    if (!query.trim()) return all
    const q = query.trim().toLocaleLowerCase('tr')
    return all.filter(
      (item) =>
        item.label.toLocaleLowerCase('tr').includes(q) ||
        item.sublabel?.toLocaleLowerCase('tr').includes(q),
    )
  }, [query, terms, coursesByTerm])

  if (!open) return null

  const go = (item: PaletteItem) => {
    navigate(item.to)
    close()
  }

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 p-4 pt-[15vh] backdrop-blur-sm"
      onClick={() => close()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Komut paleti"
        className="glass-panel w-full max-w-md overflow-hidden p-0"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-stuhub-border px-4 py-3">
          <MagnifyingGlass size={18} className="shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelected(0)
            }}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') {
                event.preventDefault()
                setSelected((s) => Math.min(s + 1, items.length - 1))
              } else if (event.key === 'ArrowUp') {
                event.preventDefault()
                setSelected((s) => Math.max(s - 1, 0))
              } else if (event.key === 'Enter' && items[selected]) {
                event.preventDefault()
                go(items[selected])
              }
            }}
            placeholder="Dönem veya ders ara…"
            aria-label="Dönem veya ders ara"
            className="w-full bg-transparent text-sm text-stuhub-text placeholder:text-stuhub-text-muted focus:outline-none"
          />
          <kbd className="shrink-0 rounded-control border border-stuhub-border px-1.5 py-0.5 text-xs text-stuhub-text-muted">
            Esc
          </kbd>
        </div>
        <ul role="listbox" className="max-h-80 overflow-y-auto p-2">
          {items.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-stuhub-text-secondary">Sonuç yok.</li>
          )}
          {items.map((item, index) => (
            <li key={item.id}>
              <button
                type="button"
                role="option"
                aria-selected={index === selected}
                onMouseEnter={() => setSelected(index)}
                onClick={() => go(item)}
                className={`flex w-full items-center justify-between gap-3 rounded-control px-3 py-2 text-left text-sm ${
                  index === selected
                    ? 'bg-stuhub-accent-glass text-stuhub-text'
                    : 'text-stuhub-text-secondary hover:text-stuhub-text'
                }`}
              >
                <span className="truncate">{item.label}</span>
                {item.sublabel && (
                  <span className="shrink-0 truncate text-xs text-stuhub-text-muted">{item.sublabel}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
