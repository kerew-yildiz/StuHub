import { useGenerationStore } from '../stores/generationStore'
import { useAnimatedProgress } from '../lib/useAnimatedProgress'

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

/** Her sayfada görünen küresel üretim paneli — aktif işler + ilerleme (madde 2). */
export function GlobalGenerationPanel() {
  const jobs = useGenerationStore((s) => s.jobs)

  if (jobs.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-40 w-72 space-y-2">
      {jobs.map((job) => (
        <JobRow key={`${job.kind}-${job.targetId}`} kind={job.kind} targetId={job.targetId} />
      ))}
    </div>
  )
}
