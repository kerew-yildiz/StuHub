import { lazy, Suspense, useEffect } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

import { AlertDialog } from './components/AlertDialog'
import { CommandPalette } from './components/CommandPalette'
import { ConfirmDialog } from './components/ConfirmDialog'
import { GlobalGenerationPanel } from './components/GlobalGenerationPanel'
import { HealthBanner } from './components/HealthBanner'
import { HelpPanel } from './components/HelpPanel'
import { Sidebar } from './components/Sidebar'
import { supabaseClient } from './lib/supabaseClient'
import { LoginPage } from './pages/LoginPage'
import { useAuthStore } from './stores/authStore'
import { usePaletteStore } from './stores/paletteStore'

// Rota bazlı code-splitting: sayfalar (+ pdfjs-dist/motion gibi ağır bağımlılıkları)
// yalnızca ziyaret edilince indirilir. Öncesinde tek bir 844KB paket her sayfada
// tamamen indiriliyordu (2026-09-05 perf turunda ölçüldü, Vite build uyarısı verdi).
// `LoginPage` hariç — router'dan önce, kimlik doğrulanmamışken anında gösterilmesi
// gerekiyor, geciktirmek gecikme ekler.
const TermsPage = lazy(() => import('./pages/TermsPage').then((m) => ({ default: m.TermsPage })))
const TermDetailPage = lazy(() =>
  import('./pages/TermDetailPage').then((m) => ({ default: m.TermDetailPage })),
)
const CoursePage = lazy(() => import('./pages/CoursePage').then((m) => ({ default: m.CoursePage })))
const NotebookPage = lazy(() =>
  import('./pages/NotebookPage').then((m) => ({ default: m.NotebookPage })),
)
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
const SavedQuestionsPage = lazy(() =>
  import('./pages/SavedQuestionsPage').then((m) => ({ default: m.SavedQuestionsPage })),
)

export default function App() {
  const loading = useAuthStore((s) => s.loading)
  const saasMode = useAuthStore((s) => s.saasMode)
  const session = useAuthStore((s) => s.session)
  const init = useAuthStore((s) => s.init)
  const togglePalette = usePaletteStore((s) => s.toggle)

  useEffect(() => {
    void init()
  }, [init])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-stuhub-text">
        <p className="text-sm text-stuhub-text-secondary">Yükleniyor…</p>
      </div>
    )
  }

  if (saasMode && !session) {
    return <LoginPage />
  }

  return (
    <div className="min-h-[100dvh] text-stuhub-text">
      <Sidebar />
      <div className="md:pl-64">
        <header className="sticky top-0 z-40 border-b border-stuhub-border bg-stuhub-bg/70 backdrop-blur-2xl">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link to="/" className="text-2xl font-semibold tracking-tight">
              StuHub
            </Link>
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={togglePalette}
                className="glass-panel-subtle glass-interactive hidden items-center gap-2 rounded-control px-3 py-1.5 text-sm text-stuhub-text-secondary sm:flex"
              >
                <span>Ara</span>
                <kbd className="rounded-control border border-stuhub-border px-1.5 py-0.5 text-xs text-stuhub-text-muted">
                  Ctrl K
                </kbd>
              </button>
              <HelpPanel />
              {saasMode && session && (
                <button
                  type="button"
                  onClick={() => void supabaseClient?.auth.signOut()}
                  className="text-sm text-stuhub-text-secondary transition-colors duration-[var(--duration-micro)] hover:text-stuhub-text"
                >
                  Çıkış yap
                </button>
              )}
            </div>
          </div>
        </header>
        <HealthBanner />
        <GlobalGenerationPanel />
        <main className="mx-auto max-w-5xl px-6 py-8">
          <Suspense
            fallback={<p className="py-8 text-sm text-stuhub-text-secondary">Yükleniyor…</p>}
          >
            <Routes>
              <Route path="/" element={<TermsPage />} />
              <Route path="/donemler/:termId" element={<TermDetailPage />} />
              <Route path="/dersler/:courseId" element={<CoursePage />} />
              <Route
                path="/dersler/:courseId/defter/:chapterId"
                element={<NotebookPage />}
              />
              <Route path="/ayarlar" element={<SettingsPage />} />
              <Route path="/kaydedilenler" element={<SavedQuestionsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
      <ConfirmDialog />
      <AlertDialog />
      <CommandPalette />
    </div>
  )
}
