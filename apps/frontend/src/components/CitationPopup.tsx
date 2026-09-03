import { X } from '@phosphor-icons/react'
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
  web: 'Web',
}

/** URL'yi güvenli biçimde render eder — yalnızca http(s) ise tıklanabilir bağlantı. */
function SourceUrl({ url }: { url: string }) {
  if (/^https?:\/\//i.test(url)) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="mt-1 inline-block break-all text-stuhub-accent underline decoration-stuhub-accent/40 underline-offset-2 transition-colors duration-150 hover:text-stuhub-accent-hover"
      >
        {url}
      </a>
    )
  }
  return <p className="mt-1 break-all text-stuhub-text-secondary">{url}</p>
}

/** Atıf pop-up'ı — kaynak parçayı gösterir (Yetenek 06 §3; metin fallback). */
export function CitationPopup({ citation, onClose, preloadedText, sourceLabel }: CitationPopupProps) {
  const [chunk, setChunk] = useState<ResolvedChunk | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const isWeb = citation.source_type === 'web' || Boolean(citation.url)

  useEffect(() => {
    // Web atıflarında kaynak parça API'den gelmez — doğrudan alıntı + URL gösterilir.
    if (preloadedText || isWeb) return undefined
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
  }, [citation.chunk_id, citation.url, citation.source_type, preloadedText, isWeb])

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
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto glass-panel p-6"
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
            className="rounded-control p-1.5 text-stuhub-text-secondary transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-glass-1-hover hover:text-stuhub-text active:scale-[0.98]"
            aria-label="Kapat"
          >
            <X size={18} aria-hidden="true" />
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
          {isWeb ? (
            citation.url && (
              <div>
                <p className="font-medium text-stuhub-text-secondary">Kaynak</p>
                <SourceUrl url={citation.url} />
              </div>
            )
          ) : (
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
          )}
        </div>
      </div>
    </div>
  )
}
