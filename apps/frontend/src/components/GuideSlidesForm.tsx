import { useRef, useState } from 'react'

interface GuideSlidesFormProps {
  onUpload: (file: File) => Promise<void>
}

/** Chapter guide slides yükleme formu (PDF / PPTX — Faz 2.1). */
export function GuideSlidesForm({ onUpload }: GuideSlidesFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!file) {
      setError('Lütfen bir sunum dosyası seç.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onUpload(file)
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch {
      setError('Sunum yüklenemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="glass-panel space-y-4 p-6">
      <div className="flex items-end gap-4">
        <div className="flex-1">
          <label htmlFor="guide-slides-file" className="mb-1 block text-sm font-medium">Sunum dosyası (PDF / PPTX)</label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="glass-panel-subtle glass-interactive shrink-0 rounded-control px-3 py-2 text-sm font-medium text-stuhub-text-secondary"
            >
              Dosya Seç
            </button>
            <span className="min-w-0 truncate text-sm text-stuhub-text-secondary">
              {file ? file.name : 'Dosya seçilmedi'}
            </span>
          </div>
          <input
            id="guide-slides-file"
            ref={inputRef}
            type="file"
            accept=".pdf,.pptx,.ppt"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
          <p className="mt-1 text-xs text-stuhub-text-secondary">
            Bu sunum, chapter notlarının rehberi olarak kullanılacak (guide slides). Birden
            fazla sunum yükleyebilirsin.
          </p>
          <p className="mt-1 text-xs font-medium text-stuhub-info">
            Bu sunum, mevcut slaytlara EKLENİR.
          </p>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
        >
          {busy ? 'Yükleniyor…' : 'Yükle'}
        </button>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
    </form>
  )
}
