import { useCallback, useEffect, useState } from 'react'

import { termsApi, type Term, type TermInput } from '../api/terms'
import { AddContentCard } from '../components/AddContentCard'
import { StreakRing } from '../components/StreakRing'
import { TermCard } from '../components/TermCard'
import { TermForm } from '../components/TermForm'
import { confirmDialog } from '../stores/confirmStore'

type LoadState = 'loading' | 'ready' | 'error'

/** Dönem düzenleme mini formu — ad + tarih aralığı (hafif, mevcut Form'dan bağımsız). */
function TermEditForm({
  term,
  onSubmit,
  onCancel,
}: {
  term: Term
  onSubmit: (input: TermInput) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(term.name)
  const [startDate, setStartDate] = useState(term.start_date?.slice(0, 10) ?? '')
  const [endDate, setEndDate] = useState(term.end_date?.slice(0, 10) ?? '')
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
    } catch {
      setError('Dönem güncellenemedi. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-panel space-y-3 p-4"
    >
      <div>
        <label htmlFor={`term-edit-name-${term.id}`} className="mb-1 block text-sm font-medium">
          Dönem adı
        </label>
        <input
          id={`term-edit-name-${term.id}`}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor={`term-edit-start-${term.id}`} className="mb-1 block text-sm font-medium">
            Başlangıç
          </label>
          <input
            id={`term-edit-start-${term.id}`}
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
          />
        </div>
        <div>
          <label htmlFor={`term-edit-end-${term.id}`} className="mb-1 block text-sm font-medium">
            Bitiş
          </label>
          <input
            id={`term-edit-end-${term.id}`}
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent"
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
          İptal
        </button>
      </div>
    </form>
  )
}

/** Dönemler ana sayfası (Faz 1.1) + streak halkası. */
export function TermsPage() {
  const [terms, setTerms] = useState<Term[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingTerm, setEditingTerm] = useState<Term | null>(null)

  const load = useCallback(async () => {
    setState('loading')
    try {
      setTerms(await termsApi.list())
      setState('ready')
    } catch {
      setState('error')
      setError('Dönemler yüklenemedi. Lütfen tekrar deneyin.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreate = async (input: TermInput) => {
    await termsApi.create(input)
    setShowForm(false)
    await load()
  }

  const handleUpdate = async (id: number, input: TermInput) => {
    await termsApi.update(id, input)
    setEditingTerm(null)
    await load()
  }

  const handleDelete = async (id: number) => {
    const term = terms.find((t) => t.id === id)
    if (!term) return
    if (!(await confirmDialog(`"${term.name}" dönemi ve içindeki dersler silinecek. Emin misin?`))) {
      return
    }
    try {
      await termsApi.remove(id)
      setTerms((prev) => prev.filter((t) => t.id !== id))
    } catch {
      setError('Dönem silinemedi. Lütfen tekrar deneyin.')
    }
  }

  return (
    <section className="page-shell">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dönemler</h1>
          <p className="page-subtitle">Ders dönemlerini buradan yönetebilirsin.</p>
        </div>
      </div>
      <StreakRing />

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
        <div className="flex flex-wrap items-center gap-3">
          {!showForm && (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="btn-primary"
            >
              Yeni dönem
            </button>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {showForm && (
        <div className="mt-6">
          <TermForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      {/* Sıkıntı #3: dönem kartları büyük hücreler — dar sütunlarda sıramasın */}
      <div className="term-grid mt-8">
        {state === 'loading' && (
          <p className="text-sm text-stuhub-text-secondary">Dönemler yükleniyor…</p>
        )}
        {state === 'ready' && terms.length === 0 && !showForm && (
          <AddContentCard
            label="Dönem ekle"
            description="Henüz dönem yok — ilk dönemini oluşturarak başla."
            variant="term"
            onClick={() => setShowForm(true)}
          />
        )}
        {terms.map((term) => (
          <div key={term.id} className="max-w-[420px] space-y-3">
            <TermCard term={term} onDelete={handleDelete} onEdit={setEditingTerm} />
            {editingTerm?.id === term.id && (
              <TermEditForm
                term={term}
                onSubmit={(input) => handleUpdate(term.id, input)}
                onCancel={() => setEditingTerm(null)}
              />
            )}
          </div>
        ))}
        {terms.length > 0 && !showForm && (
          <AddContentCard
            label="Dönem ekle"
            description="Yeni bir dönem oluştur ve derslerini ekle."
            variant="term"
            onClick={() => setShowForm(true)}
          />
        )}
      </div>
    </section>
  )
}
