import { X } from '@phosphor-icons/react'
import { useState } from 'react'

import type { Slide } from '../api/slides'

interface SlidePreviewProps {
  slides: Slide[]
  onDelete: (slideId: number) => void
}

/** Slide önizleyici (metin yedeği) — PDF yoksa slaytları teker teker kart olarak gösterir. */
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
    <div className="glass-panel overflow-hidden">
      {/* Slide kartı */}
      <div className="flex min-h-[12rem] items-center justify-center px-10 py-8">
        <p className="max-w-2xl text-center text-base leading-relaxed text-stuhub-text">
          {slide.content_text ? slide.content_text : '(Bu slide da metin yok)'}
        </p>
      </div>

      <div className="flex items-center justify-between border-t border-stuhub-border px-4 py-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIndex((i) => Math.max(0, i - 1))}
            disabled={current === 0}
            className="rounded-control px-2 py-1 text-base text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover active:scale-[0.98] disabled:opacity-40 disabled:active:scale-100"
            aria-label="Önceki slide"
          >
            ‹
          </button>
          <span className="min-w-[3.5rem] text-center text-sm font-medium tabular-nums">
            {current + 1} / {slides.length}
          </span>
          <button
            type="button"
            onClick={() => setIndex((i) => Math.min(slides.length - 1, i + 1))}
            disabled={current === slides.length - 1}
            className="rounded-control px-2 py-1 text-base text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover active:scale-[0.98] disabled:opacity-40 disabled:active:scale-100"
            aria-label="Sonraki slide"
          >
            ›
          </button>
        </div>
        <button
          type="button"
          onClick={() => onDelete(slide.id)}
          className="rounded-control p-1.5 text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-error/10 hover:text-stuhub-error"
          title="Sil"
          aria-label={`Slide ${current + 1} sil`}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
