import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, ChevronRight, Clock, Hourglass, Pencil, RotateCcw, Timer, X } from 'lucide-react'

import { getCardSummary, type ChapterCardSummary, type CourseCardSummary } from '../api/cardSummary'
import type { Chapter } from '../api/chapters'
import type { Course } from '../api/courses'

/** Saniyeyi "18 sa 42 dk" biçimine çevirir. */
function formatDuration(totalSec: number): string {
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.round((totalSec % 3600) / 60)
  if (hours === 0) return `${minutes} dk`
  if (minutes === 0) return `${hours} sa`
  return `${hours} sa ${minutes} dk`
}

/** ISO zamanı "2 saat önce" benzeri göreli metne çevirir. */
function formatRelative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'şimdi'
  if (minutes < 60) return `${minutes} dk önce`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} sa önce`
  return `${Math.round(hours / 24)} gün önce`
}

/** Progress bar + yüzdesi — monochrome luminosity (§36). */
export function ProgressBar({ value }: { value: number | null }) {
  if (value === null) return null
  const percent = Math.round(value * 100)
  return (
    <div className="card-progress" aria-label={`İlerleme %${percent}`}>
      <span className="card-progress__track">
        <span className="card-progress__fill" style={{ width: `${percent}%` }} />
      </span>
      <span className="card-progress__value">%{percent}</span>
    </div>
  )
}

/** Ders kartı (yönerge §36):
 *
 * NORMAL  : Ders adı + Progress + yaklaşan sınav
 * HOVER 1 : Son aktivite + toplam çalışma
 * HOVER 2 (2 sn sonra): Tamamlanan chapter + progress
 * Hover çıkışı → normal. Kart geometrisi sabit; layout zıplamaz.
 *
 * `onEdit`/`onDelete` verilirse sağ üstte düzenle/sil ikonları gösterilir.
 */
export function CourseCard({
  course,
  onEdit,
  onDelete,
}: {
  course: Course
  onEdit?: (course: Course) => void
  onDelete?: (course: Course) => void
}) {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<CourseCardSummary | null>(null)
  const [hovered, setHovered] = useState(false)
  const [rotation, setRotation] = useState(0) // 0: normal, 1: state 1, 2: state 2
  const hoverTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    getCardSummary(course.id)
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [course.id])

  useEffect(() => {
    window.clearTimeout(hoverTimer.current)
    if (!hovered) {
      setRotation(0)
      return
    }
    setRotation(1)
    hoverTimer.current = window.setTimeout(() => setRotation(2), 2000)
    return () => window.clearTimeout(hoverTimer.current)
  }, [hovered])

  const showExam = summary?.next_exam && rotation === 0
  const showActivity = summary?.last_activity && rotation >= 1 && rotation < 2

  return (
    <div
      role="link"
      tabIndex={0}
      aria-label={`${course.name} dersini aç`}
      onClick={() => navigate(`/dersler/${course.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/dersler/${course.id}`)
        }
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="glass-panel glass-interactive course-card"
    >
      <div className="min-w-0">
        <h2 className="text-lg font-semibold">{course.name}</h2>
        {course.instructor && (
          <p className="mt-0.5 truncate text-sm text-stuhub-text-secondary">{course.instructor}</p>
        )}
      </div>

      {(onEdit || onDelete) && (
        <span
          className="absolute right-2.5 top-2.5 flex items-center gap-1"
          onClick={(e) => e.stopPropagation()}
        >
          {onEdit && (
            <button
              type="button"
              onClick={() => onEdit(course)}
              className="icon-btn"
              title="Düzenle"
              aria-label={`${course.name} dersini düzenle`}
            >
              <Pencil size={15} aria-hidden="true" />
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(course)}
              className="icon-btn icon-btn--danger"
              title="Sil"
              aria-label={`${course.name} dersini sil`}
            >
              <X size={15} aria-hidden="true" />
            </button>
          )}
        </span>
      )}

      <div className="card-meta-stack">
        {rotation === 0 && (
          <>
            <ProgressBar value={summary ? summary.progress : null} />
            {showExam ? (
              <p className="card-meta" title={summary!.next_exam!.title}>
                <Hourglass size={13} aria-hidden="true" />
                {`${summary!.next_exam!.title} · ${new Date(`${summary!.next_exam!.exam_date}T12:00:00`).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })} · ${summary!.next_exam!.days_left} gün`}
              </p>
            ) : (
              <p className="card-meta card-meta--faded">
                {summary ? `${summary.total_chapters} chapter` : '—'}
              </p>
            )}
          </>
        )}
        {rotation === 1 && (
          <>
            {showActivity && (
              <p className="card-meta">
                <RotateCcw size={13} aria-hidden="true" />
                <span>
                  {`Son aktivite · ${summary!.last_activity!.label ?? summary!.last_activity!.kind} · ${formatRelative(summary!.last_activity!.at)}`}
                </span>
              </p>
            )}
            <p className="card-meta">
              <Timer size={13} aria-hidden="true" />
              <span>{`Toplam çalışma · ${formatDuration(summary?.total_study_sec ?? 0)}`}</span>
            </p>
          </>
        )}
        {rotation === 2 && (
          <>
            <p className="card-meta">
              <Check size={13} aria-hidden="true" />
              <span>{`Tamamlanan chapter · ${summary?.completed_chapters ?? 0} / ${summary?.total_chapters ?? 0}`}</span>
            </p>
            <ProgressBar value={summary ? summary.progress : null} />
          </>
        )}
      </div>
    </div>
  )
}

/** Chapter kartı (yönerge §37): normal ad+progress, hover rotation topic/aktivite,
 * tamamlanmışsa check. Hover'da chapter'da geçen toplam çalışma süresi de gösterilir
 * (ders kartındaki etiketle aynı biçim). Exam/ödev metadata TAŞIMAZ.
 * `onEdit`/`onDelete` verilirse sağ üstte düzenle/sil ikonları gösterilir. */
export function ChapterCard({
  chapter,
  summary,
  onEdit,
  onDelete,
}: {
  chapter: Chapter
  summary: ChapterCardSummary | null
  onEdit?: (chapter: Chapter) => void
  onDelete?: (chapter: Chapter) => void
}) {
  const navigate = useNavigate()
  const [hovered, setHovered] = useState(false)
  const hoverTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!hovered) {
      return
    }
    const timer = hoverTimer.current
    return () => window.clearTimeout(timer)
  }, [hovered])

  const completed = summary !== null && summary.topics_total > 0 && summary.topics_completed >= summary.topics_total

  return (
    <div
      role="link"
      tabIndex={0}
      aria-label={`${chapter.title} chapter'ını aç`}
      onClick={() => navigate(`/dersler/${chapter.course_id}/defter/${chapter.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/dersler/${chapter.course_id}/defter/${chapter.id}`)
        }
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="glass-panel glass-interactive chapter-card"
    >
      <div className="chapter-card__head">
        {completed && (
          <span className="chapter-card__check" title="Tamamlandı" aria-label="Tamamlandı">
            <Check size={14} aria-hidden="true" />
          </span>
        )}
        <span className="chapter-card__title">{chapter.title}</span>
        {(onEdit || onDelete) && (
          <span className="chapter-card__actions" onClick={(e) => e.stopPropagation()}>
            {onEdit && (
              <button
                type="button"
                onClick={() => onEdit(chapter)}
                className="icon-btn"
                title="Düzenle"
                aria-label={`${chapter.title} chapter'ını düzenle`}
              >
                <Pencil size={15} aria-hidden="true" />
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={() => onDelete(chapter)}
                className="icon-btn icon-btn--danger"
                title="Sil"
                aria-label={`${chapter.title} chapter'ını sil`}
              >
                <X size={15} aria-hidden="true" />
              </button>
            )}
          </span>
        )}
      </div>

      {hovered && summary ? (
        <div className="card-meta-stack">
          <p className="card-meta">
            <Check size={13} aria-hidden="true" />
            <span>{`Tamamlanan topic · ${summary.topics_completed} / ${summary.topics_total}`}</span>
          </p>
          {summary.last_activity && (
            <p className="card-meta">
              <Clock size={13} aria-hidden="true" />
              <span>{`Son aktivite · ${formatRelative(summary.last_activity)}`}</span>
            </p>
          )}
          <p className="card-meta">
            <Timer size={13} aria-hidden="true" />
            <span>{`Toplam çalışma · ${formatDuration(summary.total_study_sec ?? 0)}`}</span>
          </p>
        </div>
      ) : (
        <ProgressBar value={summary && summary.topics_total > 0 ? summary.topics_completed / summary.topics_total : null} />
      )}
      <ChevronRight className="chapter-card__go" size={16} aria-hidden="true" />
    </div>
  )
}
