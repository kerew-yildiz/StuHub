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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-end gap-4">
        <div className="flex-1">
          <label htmlFor="guide-slides-file" className="mb-1 block text-sm font-medium">
            Sunum dosyası (PDF / PPTX)
          </label>
          <input
            id="guide-slides-file"
            ref={inputRef}
            type="file"
            accept=".pdf,.pptx,.ppt"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
          <p className="mt-1 text-xs text-stuhub-text-secondary">
            Bu sunum, chapter notlarının rehberi olarak kullanılacak (guide slides).
          </p>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-60"
        >
          {busy ? 'Yükleniyor…' : 'Yükle'}
        </button>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
    </form>
  )
}
