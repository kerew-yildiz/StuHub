import { useRef, useState } from 'react'

interface GuideSlidesFormProps {
  onUpload: (file: File) => Promise<void>
}

/** Chapter guide slides yükleme formu (PDF / PPTX / PPT — Faz 2.1). Kendi kart zemini
 * taşımaz — çağıran yer (`glass-panel`/`PostCreatePrompt`) sağlar, iç içe kart olmasın. */
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
    <form onSubmit={handleSubmit} className="space-y-3">
      <label htmlFor="guide-slides-file" className="mb-1 block text-sm font-medium">
        Sunum dosyası (PDF / PPTX)
      </label>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="btn-primary shrink-0"
        >
          Dosya Seç
        </button>
        <span className="min-w-0 truncate text-sm text-stuhub-text-secondary">
          {file ? file.name : 'Dosya seçilmedi'}
        </span>
        <input
          id="guide-slides-file"
          ref={inputRef}
          type="file"
          accept=".pdf,.pptx,.ppt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="hidden"
        />
        <button type="submit" disabled={!file || busy} className="btn-primary sm:ml-auto">
          {busy ? 'Yükleniyor…' : 'Yükle'}
        </button>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
    </form>
  )
}
