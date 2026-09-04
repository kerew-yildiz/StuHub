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
      className="glass-panel space-y-4 p-6"
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
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
        />
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="btn-primary"
        >
          {busy ? 'Oluşturuluyor…' : 'Oluştur'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
        >
          Vazgeç
        </button>
      </div>
    </form>
  )
}
