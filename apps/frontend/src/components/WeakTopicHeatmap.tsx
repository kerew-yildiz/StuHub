import { GridFour, Thermometer } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'

import { getHeatmap, type CourseHeatmap } from '../api/heatmap'

export interface WeakTopicHeatmapProps {
  courseId: number
}

/** Backend `CHAT_SATURATION` ile aynı doyum noktası — chat baskısını 0..1'e indirger. */
const CHAT_SATURATION = 5

/** Zayıflık yoğunluğu kademesi — monochrome: renk skalası değil, beyaz aksanın
 * opaklık kademesi (TASARIM-SISTEMI.md §1 "tek aksan: beyaz, vurgu yoğunlukla"). */
const HEAT_STEPS = [
  'bg-stuhub-accent/5 border-stuhub-border text-stuhub-text-secondary',
  'bg-stuhub-accent/10 border-stuhub-border text-stuhub-text-secondary',
  'bg-stuhub-accent/15 border-stuhub-border-strong text-stuhub-text',
  'bg-stuhub-accent/20 border-stuhub-border-strong text-stuhub-text',
  'bg-stuhub-accent/25 border-stuhub-border-strong text-stuhub-text',
]

/** Veri olmayan hücre — kademe dışı, kenarlık + susturulmuş metin. */
const EMPTY_CELL = 'border-stuhub-border text-stuhub-text-muted'

/** 0..1 zayıflık → 5 kademeli opaklık sınıfı. */
function heatClass(weakness: number | null): string {
  if (weakness === null) return EMPTY_CELL
  const step = Math.min(Math.floor(weakness * HEAT_STEPS.length), HEAT_STEPS.length - 1)
  return HEAT_STEPS[step]
}

function percentLabel(ratio: number | null): string {
  return ratio === null ? '—' : `%${Math.round(ratio * 100)}`
}


const CELL_BASE =
  'flex h-9 items-center justify-center rounded-chip border font-mono text-xs tabular-nums'

const HEAD_CELL = 'text-[10px] font-medium uppercase tracking-widest text-stuhub-text-muted'

/** Zayıf konu ısı haritası — konu × (quiz doğruluğu / kart tutma / chat yoğunluğu)
 * ızgarası; hücre yoğunluğu zayıflıkla artar, en zayıf konu en üstte (Plan #18). */
export function WeakTopicHeatmap({ courseId }: WeakTopicHeatmapProps) {
  const [heatmap, setHeatmap] = useState<CourseHeatmap | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setHeatmap(null)
    setError('')
    getHeatmap(courseId)
      .then((data) => {
        if (active) setHeatmap(data)
      })
      .catch(() => {
        if (active) setError('Isı haritası yüklenemedi. Lütfen tekrar deneyin.')
      })
    return () => {
      active = false
    }
  }, [courseId])

  const header = (
    <div className="flex items-center gap-2">
      <GridFour className="h-5 w-5 text-stuhub-text-secondary" aria-hidden="true" />
      <h2 className="text-lg font-semibold">Zayıf Konu Isı Haritası</h2>
    </div>
  )

  if (error) {
    return (
      <div className="glass-panel p-5">
        {header}
        <p role="alert" className="mt-3 text-sm text-stuhub-error">
          {error}
        </p>
      </div>
    )
  }

  if (heatmap === null) {
    return (
      <div className="glass-panel p-5">
        {header}
        <div className="mt-4 space-y-2" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="glass-panel-subtle h-9 rounded-chip" />
          ))}
        </div>
      </div>
    )
  }

  if (heatmap.topics.length === 0) {
    return (
      <div className="glass-panel p-5">
        {header}
        <div className="mt-4 flex items-start gap-3">
          <Thermometer className="mt-0.5 h-5 w-5 shrink-0 text-stuhub-text-muted" aria-hidden="true" />
          <p className="text-sm text-stuhub-text-muted">
            Henüz ısı haritası çıkarılacak konu yok — bölüm notu üretin, ardından quiz çözüp
            kart tekrarlayın; sinyaller burada birleşir.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-panel p-5">
      <div className="flex items-start justify-between gap-4">
        {header}
        <p className="text-[10px] uppercase tracking-widest text-stuhub-text-muted">
          Koyu hücre = zayıf
        </p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <div className="min-w-[28rem]">
          <div className="grid grid-cols-[minmax(6rem,1fr)_repeat(4,4.25rem)] gap-2 px-1 pb-2">
            <span className={HEAD_CELL}>Konu</span>
            <span className={`${HEAD_CELL} text-center`}>Quiz</span>
            <span className={`${HEAD_CELL} text-center`}>Kart</span>
            <span className={`${HEAD_CELL} text-center`}>Chat</span>
            <span className={`${HEAD_CELL} text-center`}>Zayıflık</span>
          </div>

          <ul className="space-y-2">
            {heatmap.topics.map((topic) => {
              const sampleLabel = `${topic.topic} — örneklem: ${topic.sample_size} gözlem`
              // Her sinyalin kendi zayıflık değeri hücre yoğunluğunu belirler.
              const quizHeat = topic.quiz_accuracy === null ? null : 1 - topic.quiz_accuracy
              const cardHeat = topic.card_retention === null ? null : 1 - topic.card_retention
              // Chat tek yönlü: soru yokluğu güç kanıtı değil, veri yokluğudur (backend kuralı).
              const chatHeat =
                topic.chat_question_count === 0
                  ? null
                  : Math.min(topic.chat_question_count / CHAT_SATURATION, 1)
              return (
                <li
                  key={topic.topic}
                  className="grid grid-cols-[minmax(6rem,1fr)_repeat(4,4.25rem)] items-center gap-2"
                >
                  <span
                    className="truncate px-1 text-sm text-stuhub-text"
                    title={sampleLabel}
                    aria-label={sampleLabel}
                  >
                    {topic.topic}
                  </span>
                  <span
                    className={`${CELL_BASE} ${heatClass(quizHeat)}`}
                    title={
                      topic.quiz_accuracy === null
                        ? 'Quiz verisi yok'
                        : `Quiz doğruluğu ${percentLabel(topic.quiz_accuracy)} — örneklem: ${topic.sample_size} gözlem`
                    }
                  >
                    {percentLabel(topic.quiz_accuracy)}
                  </span>
                  <span
                    className={`${CELL_BASE} ${heatClass(cardHeat)}`}
                    title={
                      topic.card_retention === null
                        ? 'Kart tekrarı yok'
                        : `Kart tutma ${percentLabel(topic.card_retention)} — örneklem: ${topic.sample_size} gözlem`
                    }
                  >
                    {percentLabel(topic.card_retention)}
                  </span>
                  <span
                    className={`${CELL_BASE} ${heatClass(chatHeat)}`}
                    title={`Chat'te ${topic.chat_question_count} soru — örneklem: ${topic.sample_size} gözlem`}
                  >
                    {topic.chat_question_count}
                  </span>
                  <span
                    className={`${CELL_BASE} ${heatClass(topic.weakness_score)} font-semibold`}
                    title={
                      topic.weakness_score === null
                        ? `Sinyal yok — örneklem: ${topic.sample_size} gözlem`
                        : `Zayıflık ${percentLabel(topic.weakness_score)} — örneklem: ${topic.sample_size} gözlem`
                    }
                  >
                    {percentLabel(topic.weakness_score)}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      </div>

      <p className="mt-4 text-xs text-stuhub-text-muted">
        Zayıflık skoru üç sinyalin ağırlıklı birleşimidir: quiz %
        {Math.round((heatmap.weights.quiz ?? 0) * 100)}, kart %
        {Math.round((heatmap.weights.card ?? 0) * 100)}, chat %
        {Math.round((heatmap.weights.chat ?? 0) * 100)}. Verisi olmayan sinyal ağırlıktan düşer.
      </p>
    </div>
  )
}

export default WeakTopicHeatmap
