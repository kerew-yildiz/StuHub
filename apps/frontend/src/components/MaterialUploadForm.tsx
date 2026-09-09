import { useRef, useState } from 'react'

interface MaterialUploadFormProps {
  onUpload: (type: 'textbook' | 'slides' | 'syllabus', file: File) => Promise<void>
  /** Verilirse tür seçici gizlenir, tür sabitlenir (örn. "ders oluşturunca kitap sor" akışı). */
  fixedType?: 'textbook' | 'slides' | 'syllabus'
}

/** Materyal yükleme formu — tür seçimi + dosya (Faz 1.2). Kendi kart zemini taşımaz —
 * çağıran yer (`glass-panel`) sağlar, iç içe kart olmasın. */
export function MaterialUploadForm({ onUpload, fixedType }: MaterialUploadFormProps) {
  const [type, setType] = useState<'textbook' | 'slides' | 'syllabus'>(fixedType ?? 'textbook')
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Toplu yüklemede kaçıncı dosyada olunduğunu gösterir — tek dosyada gösterilmez
  // (2026-09-08 kritik incelemede "Alex/power-user" bulgusu: tek seferde tek dosya
  // yükleme, birden fazla chapter'ı olan bir dersi hazırlarken yavaştı).
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (files.length === 0) {
      setError('Lütfen en az bir dosya seç.')
      return
    }
    setBusy(true)
    setError('')
    const failed: string[] = []
    for (let i = 0; i < files.length; i += 1) {
      setProgress(files.length > 1 ? { done: i, total: files.length } : null)
      try {
        await onUpload(type, files[i])
      } catch {
        failed.push(files[i].name)
      }
    }
    setProgress(null)
    setBusy(false)
    if (failed.length > 0) {
      setError(`Yüklenemedi: ${failed.join(', ')}. Lütfen tekrar deneyin.`)
      setFiles(files.filter((f) => failed.includes(f.name)))
    } else {
      setFiles([])
      if (inputRef.current) inputRef.current.value = ''
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
              { value: 'syllabus', label: 'Müfredat (PDF / DOCX)' },
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
          {files.length === 0
            ? 'Dosya seçilmedi'
            : files.length === 1
              ? files[0].name
              : `${files.length} dosya seçildi`}
        </span>
        <input
          id="material-file"
          ref={inputRef}
          type="file"
          multiple
          accept={
            type === 'textbook'
              ? '.pdf'
              : type === 'slides'
                ? '.pdf,.pptx,.ppt'
                : '.pdf,.docx'
          }
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="hidden"
        />
        <button type="submit" disabled={files.length === 0 || busy} className="btn-primary sm:ml-auto">
          {progress ? `Yükleniyor ${progress.done + 1}/${progress.total}…` : busy ? 'Yükleniyor…' : 'Yükle'}
        </button>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
    </form>
  )
}
