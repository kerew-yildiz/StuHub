import { useState } from 'react'

import { useAnimatedProgress } from '../lib/useAnimatedProgress'
import { useGenerationStore } from '../stores/generationStore'

function JobRow({ kind, targetId }: { kind: string; targetId: number }) {
  const job = useGenerationStore((s) => s.jobs.find((j) => j.kind === kind && j.targetId === targetId))
  const progress = useAnimatedProgress(job?.percent ?? 0)

  if (!job) return null
  const isRunning = job.status === 'running'

  return (
    <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-3 shadow-lg">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="min-w-0 truncate font-medium">{job.label}</span>
        {!isRunning && job.status === 'error' ? (
          <span className="shrink-0 text-xs text-stuhub-error">Hata</span>
        ) : (
          <span className="shrink-0 text-xs text-stuhub-text-secondary">%{Math.round(progress)}</span>
        )}
      </div>
      {isRunning ? (
        <>
          <p className="mt-1 truncate text-xs text-stuhub-text-secondary">{job.message}</p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stuhub-border">
            <div
              className="h-full rounded-full bg-stuhub-accent transition-[width] duration-150 ease-out"
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
        </>
      ) : (
        <p className="mt-1 text-xs text-stuhub-text-secondary">{job.message}</p>
      )}
    </div>
  )
}

/**
 * Her sayfada görünen küresel üretim paneli (madde 2).
 * Arayüzü kısıtlamamak için kapalıyken tek satırlık kompakt bir çipe dönüşür;
 * tıklanınca tüm işlerin listesi açılır. İşler bitince panel tamamen kaybolur.
 */
export function GlobalGenerationPanel() {
  const jobs = useGenerationStore((s) => s.jobs)
  const [open, setOpen] = useState(false)

  if (jobs.length === 0) return null

  const runningJob = jobs.find((j) => j.status === 'running')
  const hasError = jobs.some((j) => j.status === 'error')

  if (!open) {
    return (
      <button
        type="button"
        role="button"
        aria-expanded={false}
        aria-label="Üretim durumunu aç"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex max-w-56 items-center gap-2 rounded-md border border-stuhub-border bg-stuhub-surface px-3 py-2 text-sm shadow-lg transition-colors duration-150 hover:bg-stuhub-surface-hover"
      >
        {runningJob ? (
          <>
            <span
              aria-hidden="true"
              className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-stuhub-accent border-t-transparent"
            />
            <span className="min-w-0 truncate font-medium">{runningJob.label}</span>
            <span className="shrink-0 text-stuhub-text-secondary">
              %{Math.round(runningJob.percent)}
            </span>
          </>
        ) : hasError ? (
          <>
            <span aria-hidden="true" className="shrink-0 text-stuhub-warning">
              ⚠
            </span>
            <span className="shrink-0 font-medium text-stuhub-text-secondary">Hata</span>
          </>
        ) : (
          <>
            <span aria-hidden="true" className="shrink-0 text-stuhub-success">
              ✓
            </span>
            <span className="min-w-0 truncate font-medium">{jobs[0].label}</span>
          </>
        )}
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 w-72 space-y-2 rounded-md border border-stuhub-border bg-stuhub-surface p-3 shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Üretim Durumu</span>
        <button
          type="button"
          aria-expanded={true}
          onClick={() => setOpen(false)}
          className="rounded-sm px-2 py-1 text-xs font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
        >
          Kapat ▾
        </button>
      </div>
      <div className="space-y-2">
        {jobs.map((job) => (
          <JobRow key={`${job.kind}-${job.targetId}`} kind={job.kind} targetId={job.targetId} />
        ))}
      </div>
    </div>
  )
}
