import { ArrowsLeftRight, Check, CircleNotch, Lightbulb, Warning } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import {
  generateComparison,
  getComparison,
  getGlossary,
  type ComparisonGuide,
} from '../api/guides'

export interface ComparisonTableProps {
  courseId: number
}

/** Backend `MAX_COMPARE_CONCEPTS` ile birebir — fazlası 422 döner. */
const MAX_CONCEPTS = 6

/** Karşılaştırma tablosu — sınavda karıştırılan kavramları yan yana koyar (plan #24). */
export function ComparisonTable({ courseId }: ComparisonTableProps) {
  const [terms, setTerms] = useState<string[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [guide, setGuide] = useState<ComparisonGuide | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    setSelected([])
    void (async () => {
      try {
        const [glossary, existing] = await Promise.all([
          getGlossary(courseId),
          getComparison(courseId),
        ])
        if (cancelled) return
        setTerms(glossary.map((entry) => entry.term))
        setGuide(existing)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Kavramlar alınamadı.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [courseId])

  const atLimit = selected.length >= MAX_CONCEPTS

  const toggle = (term: string) => {
    setSelected((current) => {
      if (current.includes(term)) return current.filter((item) => item !== term)
      if (current.length >= MAX_CONCEPTS) return current
      return [...current, term]
    })
  }

  const run = async () => {
    setGenerating(true)
    setError('')
    try {
      await generateComparison(courseId, selected)
      setGuide(await getComparison(courseId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Karşılaştırma üretilemedi.')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Kavram karşılaştırma</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Birbirine karıştırdığın kavramları seç; benzerlikleri, farkları ve en sık karıştırılan
        noktayı tablo halinde çıkarayım.
      </p>

      {loading && <p className="mt-4 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}

      {!loading && terms.length === 0 && (
        <div className="glass-panel mt-4 flex items-start gap-3 px-5 py-4">
          <Warning className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
          <p className="text-sm text-stuhub-text-secondary">
            Karşılaştırılacak kavram yok. Önce bölüm özetleri üret — kavramlar özetlerin anahtar
            terimlerinden gelir.
          </p>
        </div>
      )}

      {!loading && terms.length > 0 && (
        <div className="glass-panel-subtle mt-4 px-5 py-4">
          <p className="text-sm text-stuhub-text-secondary">
            En az 2, en fazla {MAX_CONCEPTS} kavram seç ({selected.length} seçili).
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {terms.map((term) => {
              const isSelected = selected.includes(term)
              return (
                <button
                  key={term}
                  type="button"
                  onClick={() => toggle(term)}
                  disabled={!isSelected && atLimit}
                  aria-pressed={isSelected}
                  className={`glass-interactive flex items-center gap-1.5 rounded-pill px-3.5 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 ${
                    isSelected
                      ? 'border border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
                      : 'glass-panel-subtle border border-transparent text-stuhub-text-secondary'
                  }`}
                >
                  {isSelected && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                  {term}
                </button>
              )
            })}
          </div>

          <button
            type="button"
            onClick={() => void run()}
            disabled={selected.length < 2 || generating}
            className="btn-primary mt-4 flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? (
              <CircleNotch className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowsLeftRight className="h-4 w-4" aria-hidden="true" />
            )}
            {generating ? 'Karşılaştırılıyor…' : 'Karşılaştır'}
          </button>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
        >
          {error}
        </p>
      )}

      {guide && guide.content_json.pairs.length > 0 && (
        <div className="mt-4 space-y-4">
          {guide.content_json.pairs.map((pair) => (
            <article key={`${pair.a}-${pair.b}`} className="glass-panel px-5 py-4">
              <h3 className="flex flex-wrap items-center gap-2 text-base font-semibold">
                {pair.a}
                <ArrowsLeftRight className="h-4 w-4 text-stuhub-text-secondary" aria-hidden="true" />
                {pair.b}
              </h3>

              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[32rem] border-collapse text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-stuhub-text-secondary">
                      <th scope="col" className="py-2 pr-4 font-medium">
                        Ölçüt
                      </th>
                      <th scope="col" className="py-2 pr-4 font-medium">
                        {pair.a}
                      </th>
                      <th scope="col" className="py-2 font-medium">
                        {pair.b}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pair.differences.map((difference) => (
                      <tr key={difference.aspect} className="border-t border-stuhub-border align-top">
                        <th scope="row" className="py-2 pr-4 text-left font-medium">
                          {difference.aspect}
                        </th>
                        <td className="py-2 pr-4 text-stuhub-text-secondary">{difference.a}</td>
                        <td className="py-2 text-stuhub-text-secondary">{difference.b}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pair.similarities.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs uppercase tracking-wide text-stuhub-text-secondary">
                    Ortak noktalar
                  </p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-stuhub-text-secondary">
                    {pair.similarities.map((similarity) => (
                      <li key={similarity}>{similarity}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="glass-panel-subtle mt-4 flex items-start gap-3 rounded-control px-4 py-3">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-stuhub-accent" aria-hidden="true" />
                <p className="text-sm">
                  <span className="font-medium">En sık karıştırılan: </span>
                  <span className="text-stuhub-text-secondary">{pair.confusion}</span>
                </p>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default ComparisonTable
