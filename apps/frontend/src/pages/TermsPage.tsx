import { useCallback, useEffect, useState } from 'react'

import { termsApi, type Term, type TermInput } from '../api/terms'
import { TermCard } from '../components/TermCard'
import { TermForm } from '../components/TermForm'

type LoadState = 'loading' | 'ready' | 'error'

/** Dönemler ana sayfası (Faz 1.1). */
export function TermsPage() {
  const [terms, setTerms] = useState<Term[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)

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

  const handleDelete = async (id: number) => {
    const term = terms.find((t) => t.id === id)
    if (!term) return
    if (!window.confirm(`"${term.name}" dönemi ve içindeki dersler silinecek. Emin misin?`)) {
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
    <section>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Dönemler</h1>
          <p className="mt-2 text-stuhub-text-secondary">
            Ders dönemlerini buradan yönetebilirsin.
          </p>
        </div>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
          >
            Yeni dönem
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {showForm && (
        <div className="mt-6">
          <TermForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      <div className="mt-8 space-y-4">
        {state === 'loading' && (
          <p className="text-sm text-stuhub-text-secondary">Dönemler yükleniyor…</p>
        )}
        {state === 'ready' && terms.length === 0 && (
          <div className="rounded-md border border-dashed border-stuhub-border bg-stuhub-surface p-12 text-center">
            <p className="font-medium">Henüz dönem yok</p>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              İlk dönemini oluşturarak başla.
            </p>
          </div>
        )}
        {terms.map((term) => (
          <TermCard key={term.id} term={term} onDelete={handleDelete} />
        ))}
      </div>
    </section>
  )
}
