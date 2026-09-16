import { lazy, Suspense, useEffect, useState } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'

import { useStudyTimeTracker } from './hooks/useStudyTimeTracker'

import { AlertDialog } from './components/AlertDialog'
import { AppHeader } from './components/AppHeader'
import { CommandPalette } from './components/CommandPalette'
import { ConfirmDialog } from './components/ConfirmDialog'
import { GlobalGenerationPanel } from './components/GlobalGenerationPanel'
import { HealthBanner } from './components/HealthBanner'
import { HelpPanel } from './components/HelpPanel'
import { Sidebar } from './components/Sidebar'
import { ToastHost } from './components/ToastHost'
import { LoginPage } from './pages/LoginPage'
import { useAuthStore } from './stores/authStore'
import { useShellStore } from './stores/shellStore'

const TermsPage = lazy(() => import('./pages/TermsPage').then((m) => ({ default: m.TermsPage })))
const GlobalCoursesPage = lazy(() => import('./pages/GlobalCoursesPage').then((m) => ({ default: m.GlobalCoursesPage })))
const GlobalUtilityPage = lazy(() => import('./pages/GlobalUtilityPage').then((m) => ({ default: m.GlobalUtilityPage })))
const GlobalHomePage = lazy(() => import('./pages/GlobalHomePage').then((m) => ({ default: m.GlobalHomePage })))
const PaywallPage = lazy(() => import('./pages/PaywallPage').then((m) => ({ default: m.PaywallPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })))
const TermDetailPage = lazy(() => import('./pages/TermDetailPage').then((m) => ({ default: m.TermDetailPage })))
const CoursePage = lazy(() => import('./pages/CoursePage').then((m) => ({ default: m.CoursePage })))
const NotebookPage = lazy(() => import('./pages/NotebookPage').then((m) => ({ default: m.NotebookPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const SavedQuestionsPage = lazy(() => import('./pages/SavedQuestionsPage').then((m) => ({ default: m.SavedQuestionsPage })))

function PageSkeleton() {
  return (
    <div className="content-skeleton" aria-busy="true">
      <div className="skeleton-block skeleton-block--title" />
      <div className="skeleton-grid">
        {Array.from({ length: 6 }, (_, index) => <div key={index} className="skeleton-block skeleton-block--card" />)}
      </div>
    </div>
  )
}

export default function App() {
  const loading = useAuthStore((s) => s.loading)
  const saasMode = useAuthStore((s) => s.saasMode)
  const session = useAuthStore((s) => s.session)
  const init = useAuthStore((s) => s.init)
  const workspaceFullscreen = useShellStore((s) => s.workspaceFullscreen)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Route choreography (P4): rota değişince içerik alanına rise-in replay.
  // Sınıf React state'i ile kontrol edilir — imperative class ekleme Suspense
  // re-render'ları tarafından ezilir. State-based toggle iki commit arasında
  // sınıfı gerçekten değiştirir → animasyon güvenle yeniden başlar.
  // (Tüm hooks early return'lerden ÖNCE — rules-of-hooks.)
  const location = useLocation()
  const [routeAnim, setRouteAnim] = useState(false)
  useEffect(() => {
    setRouteAnim(false)
    const raf = requestAnimationFrame(() => setRouteAnim(true))
    const t = setTimeout(() => setRouteAnim(false), 600)
    return () => { cancelAnimationFrame(raf); clearTimeout(t) }
  }, [location.pathname])

  useEffect(() => { void init() }, [init])

  // Otomatik çalışma süresi takibi (sıkıntı #2) — koşulsuz çağrılır: `failed`
  // durumundan normale dönüşte hook sayısı değişirse React "Rendered more hooks
  // than during the previous render" ile çöker.
  useStudyTimeTracker()

  if (loading) {
    return (
      <div className="app-loading">
        <img src="/brand/stuhub-logo.png" alt="StuHub" onError={(e) => { e.currentTarget.style.display = 'none' }} />
        <div className="app-loading__skeleton" />
      </div>
    )
  }

  if (saasMode && !session) return <LoginPage />


  return (
    <div className="stuhub-app">
      <Sidebar
        open={sidebarOpen}
        onHoverOpen={(value) => {
          // Hover yalnızca desktop'ta (md+) sidebar açar/kapar; mobil off-canvas kalır.
          if (window.matchMedia('(min-width: 768px)').matches) setSidebarOpen(value)
        }}
        onCloseMobile={() => setSidebarOpen(false)}
      />
      <div
        className={`app-main ${sidebarOpen ? 'app-main--sidebar-open' : 'app-main--sidebar-collapsed'} ${
          workspaceFullscreen ? 'app-main--workspace-fullscreen' : ''
        }`}
      >
        <AppHeader onMenu={() => setSidebarOpen(true)} />
        <HealthBanner />
        <GlobalGenerationPanel />
        <main className={`app-content ${routeAnim ? 'route-entering' : ''}`}>
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route path="/" element={<GlobalHomePage />} />
              <Route path="/donemler" element={<TermsPage />} />
              <Route path="/donemler/:termId" element={<TermDetailPage />} />
              <Route path="/dersler" element={<GlobalCoursesPage />} />
              <Route path="/dersler/:courseId" element={<CoursePage />} />
              <Route path="/dersler/:courseId/defter/:chapterId" element={<NotebookPage />} />
              <Route path="/takvim" element={<GlobalUtilityPage kind="calendar" />} />
              <Route path="/sinav-plani" element={<GlobalUtilityPage kind="exam-plan" />} />
              <Route path="/calisma" element={<GlobalUtilityPage kind="study-now" />} />
              <Route path="/ayarlar" element={<SettingsPage />} />
              <Route path="/paywall" element={<PaywallPage />} />
              <Route path="/kaydedilenler" element={<SavedQuestionsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
      <HelpPanel showTrigger={false} />
      <ToastHost />
      <ConfirmDialog />
      <AlertDialog />
      <CommandPalette />
    </div>
  )
}
