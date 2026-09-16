import { useRef, useState } from 'react'

import type { CourseInput } from '../api/courses'

interface CourseFormProps {
  onSubmit: (input: CourseInput, textbookFile: File, syllabusFile: File | null) => Promise<void>
  onCancel: () => void
}

/** Yeni ders formu — tek sütun, etiket üstte (stil rehberi). Ders kitabı (PDF) zorunlu,
 * müfredat (syllabus) isteğe bağlı; ikisi de ders oluşturulur oluşturulmaz yüklenir. */
export function CourseForm({ onSubmit, onCancel }: CourseFormProps) {
  const [name, setName] = useState('')
  const [instructor, setInstructor] = useState('')
  const [textbookFile, setTextbookFile] = useState<File | null>(null)
  const [syllabusFile, setSyllabusFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const textbookInputRef = useRef<HTMLInputElement>(null)
  const syllabusInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Ders adı boş olamaz.')
      return
    }
    if (!textbookFile) {
      setError('Ders kitabı (PDF) zorunlu.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit(
        { name: trimmed, instructor: instructor.trim() || null },
        textbookFile,
        syllabusFile,
      )
      setName('')
      setInstructor('')
      setTextbookFile(null)
      setSyllabusFile(null)
      if (textbookInputRef.current) textbookInputRef.current.value = ''
      if (syllabusInputRef.current) syllabusInputRef.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ders kaydedilemedi. Lütfen tekrar deneyin.')
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
        <label htmlFor="course-textbook" className="mb-1 block text-sm font-medium">
          Ders kitabı (PDF, zorunlu)
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={() => textbookInputRef.current?.click()}
            className="btn-primary shrink-0"
          >
            Dosya Seç
          </button>
          <span className="min-w-0 truncate text-sm text-stuhub-text-secondary">
            {textbookFile ? textbookFile.name : 'Dosya seçilmedi'}
          </span>
          <input
            id="course-textbook"
            ref={textbookInputRef}
            type="file"
            accept=".pdf"
            onChange={(e) => setTextbookFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
        </div>
      </div>
      <div>
        <label htmlFor="course-syllabus" className="mb-1 block text-sm font-medium">
          Müfredat (PDF/DOCX, isteğe bağlı)
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={() => syllabusInputRef.current?.click()}
            className="btn-primary shrink-0"
          >
            Dosya Seç
          </button>
          <span className="min-w-0 truncate text-sm text-stuhub-text-secondary">
            {syllabusFile ? syllabusFile.name : 'Dosya seçilmedi'}
          </span>
          <input
            id="course-syllabus"
            ref={syllabusInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => setSyllabusFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
        </div>
      </div>
      {error && <p className="text-sm text-stuhub-error">{error}</p>}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="btn-primary"
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
