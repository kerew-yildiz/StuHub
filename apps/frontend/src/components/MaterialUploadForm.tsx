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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex items-end gap-4">
        <div>
          <label htmlFor="material-type" className="mb-1 block text-sm font-medium">
            Tür
          </label>
          <select
            id="material-type"
            value={type}
            onChange={(e) => setType(e.target.value as 'textbook' | 'slides')}
            className="rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
          >
            <option value="textbook">Kitap (PDF)</option>
            <option value="slides">Sunum (PDF / PPTX)</option>
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="material-file" className="mb-1 block text-sm font-medium">
            Dosya
          </label>
          <input
            id="material-file"
            ref={inputRef}
            type="file"
            accept={type === 'textbook' ? '.pdf' : '.pdf,.pptx,.ppt'}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
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
