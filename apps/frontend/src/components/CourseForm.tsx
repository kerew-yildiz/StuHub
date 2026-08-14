import { useState } from 'react'

import type { CourseInput } from '../api/courses'

interface CourseFormProps {
  onSubmit: (input: CourseInput) => Promise<void>
  onCancel: () => void
}

/** Yeni ders formu — tek sütun, etiket üstte (stil rehberi). */
export function CourseForm({ onSubmit, onCancel }: CourseFormProps) {
  const [name, setName] = useState('')
  const [instructor, setInstructor] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Ders adı boş olamaz.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit({
        name: trimmed,
        instructor: instructor.trim() || null,
      })
      setName('')
      setInstructor('')
    } catch {
      setError('Ders kaydedilemedi. Lütfen tekrar deneyin.')
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
        <label htmlFor="course-name" className="mb-1 block text-sm font-medium">
          Ders adı
        </label>
        <input
          id="course-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Örn. Veri Yapıları"
          className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
        />
      </div>
      <div>
        <label htmlFor="course-instructor" className="mb-1 block text-sm font-medium">
          Hoca (isteğe bağlı)
        </label>
        <input
          id="course-instructor"
          type="text"
          value={instructor}
          onChange={(e) => setInstructor(e.target.value)}
          placeholder="Örn. Dr. A. Yılmaz"
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
          {busy ? 'Kaydediliyor…' : 'Kaydet'}
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
