import { useState } from 'react'

import type { Slide } from '../api/slides'

interface SlidePreviewProps {
  slides: Slide[]
  onDelete: (slideId: number) => void
}

/** Slide önizleyici — tüm slide'ları listelemek yerine teker teker gösterir (Faz 2 iyileştirme). */
export function SlidePreview({ slides, onDelete }: SlidePreviewProps) {
  const [index, setIndex] = useState(0)

  if (slides.length === 0) {
    return (
      <p className="text-sm text-stuhub-text-secondary">
        Henüz slide yok. Yukarıdan sunum yükleyerek başla.
      </p>
    )
  }

  const current = Math.min(index, slides.length - 1)
  const slide = slides[current]

  return (
    <div className="rounded-md border border-stuhub-border bg-stuhub-surface">
      <div className="flex items-center justify-between border-b border-stuhub-border px-4 py-2">
        <button
          type="button"
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          disabled={current === 0}
          className="rounded-sm px-3 py-1 text-lg text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover disabled:opacity-40"
          aria-label="Önceki slide"
        >
          ‹
        </button>
        <span className="text-sm font-medium">
          Slide {current + 1} / {slides.length}
        </span>
        <button
          type="button"
          onClick={() => setIndex((i) => Math.min(slides.length - 1, i + 1))}
          disabled={current === slides.length - 1}
          className="rounded-sm px-3 py-1 text-lg text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover disabled:opacity-40"
          aria-label="Sonraki slide"
        >
          ›
        </button>
        <button
          type="button"
          onClick={() => onDelete(slide.id)}
          className="ml-2 rounded-sm px-2 py-1 text-sm text-stuhub-error transition-colors duration-150 hover:bg-stuhub-surface-hover"
          aria-label={`Slide ${current + 1} sil`}
        >
          Sil
        </button>
      </div>

      <div className="min-h-[8rem] px-6 py-5 text-sm leading-relaxed text-stuhub-text-secondary">
        {slide.content_text ? slide.content_text : '(Bu slide da metin yok)'}
      </div>

      <div className="flex flex-wrap gap-1.5 border-t border-stuhub-border px-4 py-2">
        {slides.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setIndex(i)}
            className={`h-6 w-8 rounded-sm text-xs transition-colors duration-150 ${
              i === current
                ? 'bg-stuhub-accent text-stuhub-on-accent'
                : 'bg-stuhub-bg text-stuhub-text-secondary hover:bg-stuhub-surface-hover'
            }`}
            aria-label={`Slide ${i + 1}'e git`}
          >
            {i + 1}
          </button>
        ))}
      </div>
    </div>
  )
}
