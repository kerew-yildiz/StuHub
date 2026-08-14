import { useState } from 'react'

interface ChapterFormProps {
  onSubmit: (title: string) => Promise<void>
  onCancel: () => void
}

/** Yeni chapter formu (guide slides yükleme Faz 2.1'de). */
export function ChapterForm({ onSubmit, onCancel }: ChapterFormProps) {
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = title.trim()
    if (!trimmed) {
      setError('Chapter başlığı boş olamaz.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit(trimmed)
      setTitle('')
    } catch {
      setError('Chapter kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6"
    >
      <div>
        <label htmlFor="chapter-title" className="mb-1 block text-sm font-medium">
          Chapter başlığı
        </label>
        <input
          id="chapter-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Örn. Bağlı Listeler"
          className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
        />
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-60"
        >
          {busy ? 'Oluşturuluyor…' : 'Oluştur'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-sm px-4 py-2 text-sm font-medium text-stuhub-text-secondary transition-colors duration-150 hover:bg-stuhub-surface-hover"
        >
          Vazgeç
        </button>
      </div>
    </form>
  )
}
