import { useRef, useState } from 'react'

interface MaterialUploadFormProps {
  onUpload: (type: 'textbook' | 'slides', file: File) => Promise<void>
}

/** Materyal yükleme formu — tür seçimi + dosya (Faz 1.2). */
export function MaterialUploadForm({ onUpload }: MaterialUploadFormProps) {
  const [type, setType] = useState<'textbook' | 'slides'>('textbook')
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
    <form onSubmit={handleSubmit} className="glass-panel space-y-4 p-6">
      <div className="flex items-end gap-4">
        <div>
          <span className="mb-1 block text-sm font-medium">Tür</span>
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
        </div>
        <div className="flex-1">
          <label htmlFor="material-file" className="mb-1 block text-sm font-medium">Dosya</label>
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
            id="material-file"
            ref={inputRef}
            type="file"
            accept={type === 'textbook' ? '.pdf' : '.pdf,.pptx,.ppt'}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
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
