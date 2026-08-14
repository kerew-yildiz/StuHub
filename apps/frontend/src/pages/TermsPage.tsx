/** Dönemler ana sayfası (Faz 0.4 iskeleti — CRUD Faz 1.1'de). */

export function TermsPage() {
  return (
    <section>
      <h1 className="text-3xl font-semibold">Dönemler</h1>
      <p className="mt-2 text-stuhub-text-secondary">
        Ders dönemlerini buradan yönetebilirsin.
      </p>

      <div className="mt-8 rounded-md border border-dashed border-stuhub-border bg-stuhub-surface p-12 text-center">
        <p className="font-medium">Henüz dönem yok</p>
        <p className="mt-1 text-sm text-stuhub-text-secondary">
          İlk dönemini oluşturarak başla.
        </p>
        <button
          type="button"
          className="mt-6 rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover"
        >
          İlk dönemini oluştur
        </button>
      </div>
    </section>
  )
}
