import { Link } from 'react-router-dom'

import { Home } from 'lucide-react'

/** 404 — bilinmeyen yollar için kanonik geri dönüş sayfası (glass tasarım dili).
 * Catch-all route yokken bilinmeyen URL boş içerik alanı render ediyordu —
 * kullanıcı ne olduğunu anlamadan kaldığı yerde kalıyordu. */
export function NotFoundPage() {
  return (
    <section className="page-shell">
      <div className="glass-panel mx-auto mt-16 max-w-md p-10 text-center">
        <p className="eyebrow">404</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Sayfa bulunamadı</h1>
        <p className="mt-3 text-sm leading-relaxed text-stuhub-text-secondary">
          Aradığın sayfa taşınmış ya da hiç var olmamış olabilir. Sidebar'dan veya
          arama (Ctrl/Cmd+K) ile doğru yere gidebilirsin.
        </p>
        <Link to="/" className="btn-primary mt-6">
          <Home size={15} aria-hidden="true" /> Ana sayfaya dön
        </Link>
      </div>
    </section>
  )
}
