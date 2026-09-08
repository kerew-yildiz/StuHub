import { ArrowSquareOut, BookOpen, MagnifyingGlass } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getGlossary, type GlossaryEntry } from '../api/guides'

export interface GlossaryPanelProps {
  courseId: number
}

/** Terim sözlüğü — ders özetlerinin anahtar terimleri, alfabetik ve nota bağlantılı (plan #29). */
export function GlossaryPanel({ courseId }: GlossaryPanelProps) {
  const [entries, setEntries] = useState<GlossaryEntry[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void (async () => {
      try {
        const data = await getGlossary(courseId)
        if (!cancelled) setEntries(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Terim sözlüğü alınamadı.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [courseId])

  /** Baş harfe göre gruplanmış liste — backend zaten alfabetik döner, sıra korunur. */
  const groups = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr')
    const visible = needle
      ? entries.filter(
          (entry) =>
            entry.term.toLocaleLowerCase('tr').includes(needle) ||
            entry.definition.toLocaleLowerCase('tr').includes(needle),
        )
      : entries
    const buckets: { letter: string; items: GlossaryEntry[] }[] = []
    for (const entry of visible) {
      const letter = entry.term.slice(0, 1).toLocaleUpperCase('tr')
      const last = buckets[buckets.length - 1]
      if (last && last.letter === letter) last.items.push(entry)
      else buckets.push({ letter, items: [entry] })
    }
    return buckets
  }, [entries, query])

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Terim sözlüğü</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Ders boyunca geçen anahtar terimler tek listede. Tanımlar notlarından alınır; “Nota git”
        ile terimin ilk geçtiği yere atlarsın.
      </p>

      <label className="glass-panel-subtle mt-4 flex items-center gap-2 px-4 py-2">
        <MagnifyingGlass className="h-4 w-4 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Terim ara"
          aria-label="Terim ara"
          className="w-full bg-transparent text-sm text-stuhub-text outline-none placeholder:text-stuhub-text-secondary"
        />
      </label>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
        >
          {error}
        </p>
      )}

      {loading && <p className="mt-4 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}

      {!loading && !error && groups.length === 0 && (
        <div className="glass-panel mt-4 flex items-start gap-3 px-5 py-4">
          <BookOpen className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
          <p className="text-sm text-stuhub-text-secondary">
            {entries.length === 0
              ? 'Sözlük henüz boş. Bölüm özetleri ürettiğinde anahtar terimler burada toplanır.'
              : 'Bu aramayla eşleşen terim yok.'}
          </p>
        </div>
      )}

      {groups.map((group) => (
        <div key={group.letter} className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-stuhub-text-secondary">
            {group.letter}
          </h3>
          <dl className="mt-2 space-y-3">
            {group.items.map((entry) => (
              <div key={entry.term} className="glass-panel px-5 py-4">
                <dt className="text-sm font-semibold">{entry.term}</dt>
                <dd className="mt-1 text-sm text-stuhub-text-secondary">
                  {entry.definition || 'Bu terim notlarında henüz açıklanmamış.'}
                </dd>
                {entry.chapter_id !== null && entry.note_id !== null && (
                  <dd className="mt-3 flex flex-wrap items-center gap-2 text-xs text-stuhub-text-secondary">
                    <Link
                      to={`/dersler/${courseId}/defter/${entry.chapter_id}`}
                      className="glass-interactive glass-panel-subtle flex items-center gap-1.5 rounded-pill px-3 py-1 font-medium text-stuhub-text"
                    >
                      <ArrowSquareOut className="h-3.5 w-3.5" aria-hidden="true" />
                      Nota git
                    </Link>
                    {entry.chapter_title && <span>{entry.chapter_title}</span>}
                    {entry.heading && <span>· “{entry.heading}” başlığı altında</span>}
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </div>
      ))}
    </section>
  )
}

export default GlossaryPanel
