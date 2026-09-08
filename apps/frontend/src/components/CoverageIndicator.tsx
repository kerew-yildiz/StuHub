import { BookOpen, WarningCircle } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { getCoverage, type ChapterCoverage } from '../api/coverage'

export interface CoverageIndicatorProps {
  chapterId: number
  className?: string
}

interface PageRun {
  covered: boolean
  start: number
  end: number
}

/** Kapsanan/kapsanmayan sayfaları bitişik bloklara indirger — sayfa başına DOM düğümü
 * üretmez, 800 sayfalık kitapta da şerit birkaç elemandan oluşur. */
function pageRuns(coveredPages: number[], totalPages: number): PageRun[] {
  if (totalPages <= 0) return []
  const covered = new Set(coveredPages)
  const runs: PageRun[] = []
  for (let page = 1; page <= totalPages; page += 1) {
    const isCovered = covered.has(page)
    const last = runs[runs.length - 1]
    if (last && last.covered === isCovered) {
      last.end = page
    } else {
      runs.push({ covered: isCovered, start: page, end: page })
    }
  }
  return runs
}

/** "12–18" / tek sayfada "40" — Türkçe aralık gösterimi (kısa çizgi yerine en dash). */
function formatRange([start, end]: number[]): string {
  return start === end ? `${start}` : `${start}–${end}`
}

/** Sayfa şeridi — kapsanan bloklar dolu, kapsanmayanlar soluk; genişlik sayfa sayısıyla oranlı. */
function PageStrip({ coverage }: { coverage: ChapterCoverage }) {
  const runs = pageRuns(coverage.covered_pages, coverage.total_pages)
  const percent = Math.round(coverage.coverage_ratio * 100)

  return (
    <div
      role="img"
      aria-label={`Kaynak kapsaması yüzde ${percent}`}
      className="flex h-3 w-full overflow-hidden rounded-pill bg-stuhub-glass-2"
    >
      {runs.map((run) => (
        <div
          key={`${run.start}-${run.covered}`}
          style={{ flexGrow: run.end - run.start + 1, flexBasis: 0 }}
          title={
            run.covered
              ? `Sayfa ${formatRange([run.start, run.end])} kaynak olarak kullanıldı`
              : `Sayfa ${formatRange([run.start, run.end])} kapsanmadı`
          }
          className={run.covered ? 'bg-stuhub-accent' : 'bg-stuhub-glass-1'}
        />
      ))}
    </div>
  )
}

/** Kaynak kapsama göstergesi — notun kitabın hangi sayfalarını kullandığını gösterir (Plan #31). */
export function CoverageIndicator({ chapterId, className }: CoverageIndicatorProps) {
  const [coverage, setCoverage] = useState<ChapterCoverage | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getCoverage(chapterId)
      .then((data) => {
        if (!cancelled) setCoverage(data)
      })
      .catch(() => {
        if (!cancelled) setCoverage(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [chapterId])

  // .glass-panel-subtle zemin + kenarlık + radius'u kendi taşır (theme.css)
  const panelClass = `glass-panel-subtle p-4 ${className ?? ''}`.trim()

  if (loading) {
    return (
      <div className={panelClass}>
        <p className="text-sm text-stuhub-text-muted">Kaynak kapsaması hesaplanıyor…</p>
      </div>
    )
  }

  if (!coverage) return null

  const percent = Math.round(coverage.coverage_ratio * 100)
  const coveredCount = coverage.covered_pages.length

  return (
    <div className={panelClass}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-stuhub-text">
          <BookOpen size={16} weight="regular" className="text-stuhub-text-secondary" />
          Kaynak kapsaması
        </h3>
        {coverage.total_pages > 0 && (
          <span className="font-mono text-sm text-stuhub-text" aria-hidden="true">
            %{percent}
          </span>
        )}
      </div>

      {coverage.orphaned_source_ids.length > 0 && (
        <p className="mt-3 flex items-start gap-2 text-xs text-stuhub-warning">
          <WarningCircle size={14} weight="fill" className="mt-0.5 shrink-0" />
          Bu oran güvenilmez: not, artık bu derste bulunmayan eski bir kaynağa atıf
          yapıyor. Notu yeniden oluşturmayı dene.
        </p>
      )}

      {coverage.total_pages === 0 ? (
        <p className="mt-3 text-sm text-stuhub-text-muted">
          Sayfa bilgisi olan bir ders kitabı bulunamadı.
        </p>
      ) : (
        <>
          <div className="mt-3">
            <PageStrip coverage={coverage} />
          </div>

          <p className="mt-2 text-xs text-stuhub-text-secondary">
            {coverage.total_pages} sayfanın {coveredCount} tanesi notta kaynak olarak kullanıldı.
          </p>

          {coverage.note_id === null ? (
            <p className="mt-2 text-xs text-stuhub-text-muted">
              Bu bölüm için henüz not üretilmedi — hiçbir sayfa kaynak olarak kullanılmadı.
            </p>
          ) : coverage.uncovered_ranges.length === 0 ? (
            <p className="mt-2 text-xs text-stuhub-text-muted">
              Kitabın tüm sayfaları kaynak olarak kullanıldı.
            </p>
          ) : (
            <p className="mt-2 text-xs text-stuhub-text-muted">
              <span className="text-stuhub-text-secondary">Kapsanmayan sayfalar:</span>{' '}
              {coverage.uncovered_ranges.map(formatRange).join(', ')}
            </p>
          )}

          {coverage.materials.length > 1 && (
            <ul className="mt-3 space-y-2 border-t border-stuhub-border pt-3">
              {coverage.materials.map((material) => (
                <li key={material.material_id} className="text-xs text-stuhub-text-muted">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-stuhub-text-secondary">{material.filename}</span>
                    <span className="font-mono shrink-0 text-stuhub-text-secondary">
                      %{Math.round(material.coverage_ratio * 100)}
                    </span>
                  </div>
                  {material.uncovered_ranges.length > 0 && (
                    <span>
                      Kapsanmayan: {material.uncovered_ranges.map(formatRange).join(', ')}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

export default CoverageIndicator
