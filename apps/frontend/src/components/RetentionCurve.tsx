import { ChartLine, Info } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { getRetention, type RetentionReport, type TopicRetention } from '../api/exams'

export interface RetentionCurveProps {
  courseId: number
  /** Kaç günlük ufuk çizilsin (1..180); varsayılan backend'in 30 günü. */
  days?: number
}

/** Aynı anda çizilecek en fazla eğri — fazlası okunaksız olur, en zayıflar öne alınır. */
const MAX_CURVES = 6

const WIDTH = 640
const HEIGHT = 240
const PAD_LEFT = 44
const PAD_RIGHT = 12
const PAD_TOP = 14
const PAD_BOTTOM = 30

/* Tasarım sistemi tek aksan (beyaz) kullanır — eğriler renkle değil,
   yoğunluk + çizgi deseniyle ayrışır (bkz. TASARIM-SISTEMI.md). */
const CURVE_OPACITY = [1, 0.82, 0.66, 0.52, 0.42, 0.34]
const CURVE_DASH = ['', '6 3', '2 3', '9 4', '1 4', '7 3 2 3']

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM

function percent(value: number): string {
  return `%${Math.round(value * 100)}`
}

/** Konu eğrisini SVG `points` dizesine çevirir. */
function toPoints(topic: TopicRetention, horizon: number): string {
  const span = horizon || 1
  return topic.points
    .map((point) => {
      const x = PAD_LEFT + (point.day / span) * PLOT_W
      const y = PAD_TOP + (1 - Math.min(1, Math.max(0, point.retention))) * PLOT_H
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

/** Unutma eğrisi — konu bazlı hatırlama tahmininin zamanla düşüşü (plan #12).
 *
 * Grafik harici kütüphane olmadan, `GuideView` kavram haritasıyla aynı satır içi
 * SVG kalıbıyla çizilir. */
export function RetentionCurve({ courseId, days }: RetentionCurveProps) {
  const [report, setReport] = useState<RetentionReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void (async () => {
      try {
        const data = await getRetention(courseId, days)
        if (!cancelled) setReport(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unutma eğrisi alınamadı.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [courseId, days])

  const horizon = report?.horizon_days ?? 0
  const curves = (report?.topics ?? []).slice(0, MAX_CURVES)
  const hiddenCount = (report?.topics.length ?? 0) - curves.length
  const targetY = PAD_TOP + (1 - 0.9) * PLOT_H

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Unutma Eğrisi</h2>
      <p className="mt-1 text-sm text-stuhub-text-secondary">
        Tekrar aralıklarına göre her konuyu bugünden itibaren ne kadar hatırlayacağın tahmin
        edilir. Eğri aşağı indikçe o konu tekrar ister.
      </p>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error"
        >
          {error}
        </p>
      )}

      {loading && <p className="mt-4 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}

      {!loading && !error && curves.length === 0 && (
        <div className="glass-panel mt-4 flex items-start gap-3 px-5 py-4">
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
          <p className="text-sm text-stuhub-text-secondary">
            Eğri çizmek için önce bu derste flashcard oluştur. Kartları tekrar ettikçe eğri
            gerçek çalışma geçmişine göre şekillenir.
          </p>
        </div>
      )}

      {!loading && !error && curves.length > 0 && (
        <>
          <div className="glass-panel mt-4 overflow-x-auto p-5">
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="w-full"
              style={{ minWidth: 420 }}
              role="img"
              aria-label={`Konu bazlı unutma eğrisi, ${horizon} günlük tahmin`}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const y = PAD_TOP + (1 - ratio) * PLOT_H
                return (
                  <g key={ratio}>
                    <line
                      x1={PAD_LEFT}
                      y1={y}
                      x2={WIDTH - PAD_RIGHT}
                      y2={y}
                      style={{ stroke: 'var(--stuhub-border)', strokeWidth: 1 }}
                    />
                    <text
                      x={PAD_LEFT - 8}
                      y={y}
                      textAnchor="end"
                      dominantBaseline="central"
                      fontSize={11}
                      style={{ fill: 'var(--stuhub-text-secondary)' }}
                    >
                      {percent(ratio)}
                    </text>
                  </g>
                )
              })}

              {/* SM-2 hedefi: aralık sonunda ~%90 hatırlama */}
              <line
                x1={PAD_LEFT}
                y1={targetY}
                x2={WIDTH - PAD_RIGHT}
                y2={targetY}
                strokeDasharray="4 4"
                style={{ stroke: 'var(--stuhub-success)', strokeWidth: 1.5, opacity: 0.7 }}
              />
              <text
                x={WIDTH - PAD_RIGHT}
                y={targetY - 5}
                textAnchor="end"
                fontSize={11}
                style={{ fill: 'var(--stuhub-success)' }}
              >
                %90 tekrar hedefi
              </text>

              {curves.map((topic, index) => (
                <polyline
                  key={topic.topic}
                  points={toPoints(topic, horizon)}
                  fill="none"
                  strokeDasharray={CURVE_DASH[index] || ''}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{
                    stroke: 'var(--stuhub-accent)',
                    strokeWidth: 2,
                    opacity: CURVE_OPACITY[index] ?? 0.3,
                  }}
                />
              ))}

              {[0, Math.round(horizon / 2), horizon].map((day, index) => (
                <text
                  key={`${day}-${index}`}
                  x={PAD_LEFT + (day / (horizon || 1)) * PLOT_W}
                  y={HEIGHT - 8}
                  textAnchor={index === 0 ? 'start' : index === 2 ? 'end' : 'middle'}
                  fontSize={11}
                  style={{ fill: 'var(--stuhub-text-secondary)' }}
                >
                  {day === 0 ? 'Bugün' : `${day}. gün`}
                </text>
              ))}
            </svg>
          </div>

          <ul className="mt-3 flex flex-wrap gap-2">
            {curves.map((topic, index) => (
              <li
                key={topic.topic}
                className="glass-panel-subtle flex items-center gap-2 rounded-pill px-3 py-1.5 text-xs text-stuhub-text-secondary"
              >
                <svg width="22" height="8" aria-hidden="true">
                  <line
                    x1="0"
                    y1="4"
                    x2="22"
                    y2="4"
                    strokeDasharray={CURVE_DASH[index] || ''}
                    style={{
                      stroke: 'var(--stuhub-accent)',
                      strokeWidth: 2,
                      opacity: CURVE_OPACITY[index] ?? 0.3,
                    }}
                  />
                </svg>
                <span className="font-medium text-stuhub-text">{topic.topic}</span>
                <span>bugün {percent(topic.current)}</span>
                <span>
                  {topic.reviewed_count}/{topic.card_count} kart çalışıldı
                </span>
              </li>
            ))}
          </ul>

          <p className="mt-2 flex items-center gap-2 text-xs text-stuhub-text-secondary">
            <ChartLine className="h-4 w-4 shrink-0" aria-hidden="true" />
            {hiddenCount > 0
              ? `En zayıf ${curves.length} konu çizildi, ${hiddenCount} konu daha var.`
              : `${horizon} günlük tahmin; en zayıf konu listenin başında.`}
          </p>
        </>
      )}
    </section>
  )
}

export default RetentionCurve
