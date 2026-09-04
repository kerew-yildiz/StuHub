import { useRef, useState } from 'react'

interface MaterialUploadFormProps {
  onUpload: (type: 'textbook' | 'slides', file: File) => Promise<void>
  /** Verilirse tür seçici gizlenir, tür sabitlenir (örn. "ders oluşturunca kitap sor" akışı). */
  fixedType?: 'textbook' | 'slides'
}

/** Materyal yükleme formu — tür seçimi + dosya (Faz 1.2). Kendi kart zemini taşımaz —
 * çağıran yer (`glass-panel`/`PostCreatePrompt`) sağlar, iç içe kart olmasın. */
export function MaterialUploadForm({ onUpload, fixedType }: MaterialUploadFormProps) {
  const [type, setType] = useState<'textbook' | 'slides'>(fixedType ?? 'textbook')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!file) {
      setError('Lütfen bir dosya seç.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onUpload(type, file)
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch {
      setError('Dosya yüklenemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {!fixedType && (
        <div
          className="glass-panel-subtle inline-flex gap-1 p-1"
          role="radiogroup"
          aria-label="Materyal türü"
        >
          {(
            [
              { value: 'textbook', label: 'Kitap (PDF)' },
              { value: 'slides', label: 'Sunum (PDF / PPTX)' },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={type === option.value}
              onClick={() => setType(option.value)}
              className={`rounded-pill px-3 py-1.5 text-sm font-medium transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] active:scale-[0.98] ${
                type === option.value
                  ? 'border border-stuhub-accent-glass-border bg-stuhub-accent-glass text-stuhub-text'
                  : 'border border-transparent text-stuhub-text-secondary hover:text-stuhub-text'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
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
          id="material-file"
          ref={inputRef}
          type="file"
          accept={type === 'textbook' ? '.pdf' : '.pdf,.pptx,.ppt'}
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
