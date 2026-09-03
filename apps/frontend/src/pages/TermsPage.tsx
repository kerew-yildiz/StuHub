import { useCallback, useEffect, useRef, useState } from 'react'

import { importArchive } from '../api/archive'
import { settingsApi } from '../api/settings'
import { termsApi, type Term, type TermInput } from '../api/terms'
import { OnboardingWizard } from '../components/OnboardingWizard'
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
          className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98] disabled:opacity-60 disabled:active:scale-100"
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

/** Dönemler ana sayfası (Faz 1.1) + streak halkası + 3 adımlı onboarding (Faz V2.4). */
export function TermsPage() {
  const [terms, setTerms] = useState<Term[]>([])
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingTerm, setEditingTerm] = useState<Term | null>(null)
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null)
  const [includeFiles, setIncludeFiles] = useState(false)
  const [importing, setImporting] = useState(false)
  const [notice, setNotice] = useState('')
  const [importError, setImportError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  // Onboarding bayrağını oku — dönem listesi boşken sihirbazı açıp açmamaya karar verir.
  useEffect(() => {
    let cancelled = false
    settingsApi
      .list()
      .then((settings) => {
        if (!cancelled) setOnboardingDone(settings.onboarding_done === '1')
      })
      .catch(() => {
        if (!cancelled) setOnboardingDone(true) // bayrak okunamazsa sihirbazı zorla açma
      })
    return () => {
      cancelled = true
    }
  }, [])

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

  const handleOnboardingComplete = () => {
    setOnboardingDone(true)
    void load()
  }

  const handleImportFile = async (file: File) => {
    setImporting(true)
    setImportError('')
    setNotice('')
    try {
      const result = await importArchive(file, includeFiles)
      setNotice(`"${result.term_name}" içe aktarıldı (${result.materials_imported} materyal)`)
      await load()
    } catch (err) {
      setImportError(
        err instanceof Error ? err.message : 'Arşiv içe aktarılamadı. Lütfen tekrar deneyin.',
      )
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const showOnboarding = state === 'ready' && terms.length === 0 && onboardingDone === false

  return (
    <section>
      <StreakRing />

      <div className="mt-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Dönemler</h1>
          <p className="mt-2 text-stuhub-text-secondary">
            Ders dönemlerini buradan yönetebilirsin.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!showForm && (
            <>
              <label className="flex items-center gap-2 text-sm text-stuhub-text-secondary">
                <input
                  type="checkbox"
                  checked={includeFiles}
                  onChange={(e) => setIncludeFiles(e.target.checked)}
                />
                Materyal dosyalarıyla
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
                className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary disabled:opacity-50"
              >
                {importing ? 'İçe aktarılıyor…' : 'Arşiv İçe Aktar'}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void handleImportFile(file)
                }}
              />
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="rounded-control bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-all duration-[var(--duration-micro)] ease-[var(--ease-out-expo)] hover:bg-stuhub-accent-hover active:scale-[0.98]"
              >
                Yeni dönem
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}

      {notice && (
        <p role="status" className="mt-4 rounded-control bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success">
          {notice}
        </p>
      )}

      {importError && (
        <p role="alert" className="mt-4 rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {importError}
        </p>
      )}

      {showForm && (
        <div className="mt-6">
          <TermForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} />
        </div>
      )}

      {showOnboarding && (
        <div className="mt-8">
          <OnboardingWizard onComplete={handleOnboardingComplete} />
        </div>
      )}

      <div className="mt-8 space-y-4">
        {state === 'loading' && (
          <p className="text-sm text-stuhub-text-secondary">Dönemler yükleniyor…</p>
        )}
        {state === 'ready' && terms.length === 0 && !showOnboarding && (
          <div className="glass-panel-subtle border-dashed p-12 text-center">
            <p className="font-medium">Henüz dönem yok</p>
            <p className="mt-1 text-sm text-stuhub-text-secondary">
              İlk dönemini oluşturarak başla.
            </p>
          </div>
        )}
        {terms.map((term) => (
          <div key={term.id} className="space-y-3">
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
      </div>
    </section>
  )
}
