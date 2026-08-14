import { useEffect, useRef, useState } from 'react'

import { resolveCitation, type Citation, type ResolvedChunk } from '../api/notes'

interface CitationPopupProps {
  citation: Citation
  onClose: () => void
  /** Önceden bilinen kaynak metni (ör. chat atıfı); verilirse resolveCitation atlanır. */
  preloadedText?: string
  /** Kaynak etiketi (ör. "Kitap s.41"); verilirse alt satırda gösterilir. */
  sourceLabel?: string
}

const SOURCE_LABELS: Record<Citation['source_type'], string> = {
  textbook: 'Kitap',
  slides: 'Sunum',
  note: 'Not',
}

/** Atıf pop-up'ı — kaynak parçayı gösterir (Yetenek 06 §3; metin fallback). */
export function CitationPopup({ citation, onClose, preloadedText, sourceLabel }: CitationPopupProps) {
  const [chunk, setChunk] = useState<ResolvedChunk | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (preloadedText) return undefined
    if (citation.chunk_id) {
      let cancelled = false
      void resolveCitation(citation.chunk_id).then((resolved) => {
        if (!cancelled) setChunk(resolved)
      })
      return () => {
        cancelled = true
      }
    }
    return undefined
  }, [citation.chunk_id, preloadedText])

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const location =
    citation.source_type === 'textbook' && citation.page != null
      ? `sayfa ${citation.page}`
      : citation.source_type === 'slides' && citation.slide != null
        ? `slide ${citation.slide}`
        : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-popup-title"
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-stuhub-surface p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="citation-popup-title" className="text-lg font-semibold">
              Kaynak {location ? `· ${location}` : ''}
            </h2>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              {sourceLabel ??
                `${SOURCE_LABELS[citation.source_type]}${citation.page != null ? ` · sayfa ${citation.page}` : ''}${citation.slide != null ? ` · slide ${citation.slide}` : ''}`}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-sm px-2 py-1 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
            aria-label="Kapat"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 space-y-4 text-sm leading-relaxed">
          {citation.quote && (
            <div>
              <p className="font-medium text-stuhub-text-secondary">Alıntı</p>
              <blockquote className="mt-1 border-l-2 border-stuhub-accent pl-3 italic">
                “{citation.quote}”
              </blockquote>
            </div>
          )}
          <div>
            <p className="font-medium text-stuhub-text-secondary">Kaynak parça</p>
            {preloadedText ? (
              <p className="mt-1">{preloadedText}</p>
            ) : chunk ? (
              <p className="mt-1">{chunk.text}</p>
            ) : citation.quote ? (
              <p className="mt-1">{citation.quote}</p>
            ) : (
              <p className="mt-1 text-stuhub-text-secondary">
                Kaynak parça bulunamadı (dosya silinmiş olabilir).
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
