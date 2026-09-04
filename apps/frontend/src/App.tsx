import { useEffect } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

import { ConfirmDialog } from './components/ConfirmDialog'
import { GlobalGenerationPanel } from './components/GlobalGenerationPanel'
import { HealthBanner } from './components/HealthBanner'
import { Sidebar } from './components/Sidebar'
import { supabaseClient } from './lib/supabaseClient'
import { CoursePage } from './pages/CoursePage'
import { LoginPage } from './pages/LoginPage'
import { NotebookPage } from './pages/NotebookPage'
import { SettingsPage } from './pages/SettingsPage'
import { TermDetailPage } from './pages/TermDetailPage'
import { TermsPage } from './pages/TermsPage'
import { useAuthStore } from './stores/authStore'

export default function App() {
  const loading = useAuthStore((s) => s.loading)
  const saasMode = useAuthStore((s) => s.saasMode)
  const session = useAuthStore((s) => s.session)
  const init = useAuthStore((s) => s.init)

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
        </header>
        <HealthBanner />
        <GlobalGenerationPanel />
        <main className="mx-auto max-w-5xl px-6 py-8">
          <Routes>
            <Route path="/" element={<TermsPage />} />
            <Route path="/donemler/:termId" element={<TermDetailPage />} />
            <Route path="/dersler/:courseId" element={<CoursePage />} />
            <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
            <Route path="/ayarlar" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
      <ConfirmDialog />
    </div>
  )
}
