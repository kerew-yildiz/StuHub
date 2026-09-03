import { useState } from 'react'

import type { CourseInput } from '../api/courses'
import { COURSE_HUES, hueColorVar } from '../lib/courseColors'

interface CourseFormProps {
  onSubmit: (input: CourseInput) => Promise<void>
  onCancel: () => void
}

/** Yeni ders formu — tek sütun, etiket üstte + ders rengi seçici (stil rehberi). */
export function CourseForm({ onSubmit, onCancel }: CourseFormProps) {
  const [name, setName] = useState('')
  const [instructor, setInstructor] = useState('')
  const [hueId, setHueId] = useState<string>(COURSE_HUES[0].id)
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
        metadata_json: { hue: hueId },
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
      className="glass-panel space-y-4 p-6"
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
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
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
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
        />
      </div>
      <div>
        <span id="course-hue-label" className="mb-1 block text-sm font-medium">
          Ders rengi
        </span>
        <p className="mb-2 text-xs text-stuhub-text-secondary">
          Notlarda, kartlarda ve listede bu renk şerit olarak kullanılır.
        </p>
        <div role="radiogroup" aria-labelledby="course-hue-label" className="flex flex-wrap gap-2">
          {COURSE_HUES.map((hue) => {
            const selected = hue.id === hueId
            return (
              <button
                key={hue.id}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={hue.name}
                title={hue.name}
                onClick={() => setHueId(hue.id)}
                className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-transform duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] active:scale-95 ${
                  selected
                    ? 'scale-110 border-stuhub-accent'
                    : 'border-transparent hover:scale-105'
                }`}
                style={{ backgroundColor: hueColorVar(hue.id) }}
              >
                {selected && <span className="h-2 w-2 rounded-full bg-stuhub-bg" />}
              </button>
            )
          })}
        </div>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
        >
          {busy ? 'Kaydediliyor…' : 'Kaydet'}
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
