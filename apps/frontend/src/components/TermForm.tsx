import { useState } from 'react'

import type { TermInput } from '../api/terms'

interface TermFormProps {
  onSubmit: (input: TermInput) => Promise<void>
  onCancel: () => void
}

/** Yeni dönem formu — tek sütun, etiket üstte, hata alan altında (stil rehberi). */
export function TermForm({ onSubmit, onCancel }: TermFormProps) {
  const [name, setName] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Dönem adı boş olamaz.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await onSubmit({
        name: trimmed,
        start_date: startDate || null,
        end_date: endDate || null,
      })
      setName('')
      setStartDate('')
      setEndDate('')
    } catch {
      setError('Dönem kaydedilemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-md border border-stuhub-border bg-stuhub-surface p-6">
      <div>
        <label htmlFor="term-name" className="mb-1 block text-sm font-medium">
          Dönem adı
        </label>
        <input
          id="term-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Örn. 2026 Bahar"
          className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="term-start" className="mb-1 block text-sm font-medium">
            Başlangıç
          </label>
          <input
            id="term-start"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
          />
        </div>
        <div>
          <label htmlFor="term-end" className="mb-1 block text-sm font-medium">
            Bitiş
          </label>
          <input
            id="term-end"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
          />
        </div>
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
