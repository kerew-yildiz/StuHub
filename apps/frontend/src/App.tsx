import { NavLink, Route, Routes } from 'react-router-dom'

import { GlobalGenerationPanel } from './components/GlobalGenerationPanel'
import { HealthBanner } from './components/HealthBanner'
import { CoursePage } from './pages/CoursePage'
import { NotebookPage } from './pages/NotebookPage'
import { SettingsPage } from './pages/SettingsPage'
import { TermDetailPage } from './pages/TermDetailPage'
import { TermsPage } from './pages/TermsPage'

export default function App() {
  return (
    <div className="min-h-screen bg-stuhub-bg text-stuhub-text">
      <header className="border-b border-stuhub-border bg-stuhub-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <NavLink to="/" className="text-2xl font-semibold tracking-tight">
            StuHub
          </NavLink>
          <nav className="flex gap-6 text-sm font-medium">
            <NavLink
              to="/"
              className="text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
            >
              Dönemler
            </NavLink>
            <NavLink
              to="/ayarlar"
              className="text-stuhub-text-secondary transition-colors duration-150 hover:text-stuhub-text"
            >
              Ayarlar
            </NavLink>
          </nav>
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
  )
}
