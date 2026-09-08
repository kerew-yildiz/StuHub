import { X } from '@phosphor-icons/react'
import { useEffect, useRef } from 'react'

import { useAuthedFileUrl } from '../lib/useAuthedFileUrl'

interface FilePreviewModalProps {
  /** `authFetch` kuralına uygun `/api` ÖNEKSİZ yol (örn. `/materials/5/file`). */
  path: string
  title: string
  /** PDF'i belirli sayfada açar (`#page=N`); verilmezse dosya baştan açılır. */
  page?: number
  onClose: () => void
}

/** Dosya önizleme penceresi — PDF'leri tarayıcı görüntüleyicisiyle açar (Faz iyileştirme).
 *
 * SaaS modda `Authorization` başlığı gerektiği için (`<iframe src>` başlık taşıyamaz)
 * dosya önce `authFetch` ile blob olarak indirilir, sonra `blob:` URL'i iframe'e verilir
 * (bkz. `lib/useAuthedFileUrl.ts`). */
export function FilePreviewModal({ path, title, page, onClose }: FilePreviewModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const { blobUrl, loading, error } = useAuthedFileUrl(path)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="file-preview-title"
        className="flex max-h-[90vh] w-full max-w-4xl flex-col glass-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-stuhub-border px-5 py-3">
          <h2 id="file-preview-title" className="truncate text-base font-semibold">
            {title}
          </h2>
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
        {error ? (
          <p className="flex h-[75vh] w-full items-center justify-center text-sm text-stuhub-text-secondary">
            Dosya yüklenemedi. Lütfen tekrar deneyin.
          </p>
        ) : loading || !blobUrl ? (
          <p className="flex h-[75vh] w-full items-center justify-center text-sm text-stuhub-text-secondary">
            Yükleniyor…
          </p>
        ) : (
          <iframe
            src={page != null ? `${blobUrl}#page=${page}` : blobUrl}
            title={title}
            className="h-[75vh] w-full bg-white"
          />
        )}
      </div>
    </div>
  )
}
