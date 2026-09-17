import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'

import { AlertDialog } from './components/AlertDialog'
import { AppHeader } from './components/AppHeader'
import { CommandPalette } from './components/CommandPalette'
import { ConfirmDialog } from './components/ConfirmDialog'
import { CursorRing } from './components/CursorRing'
import { GlobalGenerationPanel } from './components/GlobalGenerationPanel'
import { HealthBanner } from './components/HealthBanner'
import { HelpPanel } from './components/HelpPanel'
import { Sidebar } from './components/Sidebar'
import { StudyTimeTracker } from './components/StudyTimeTracker'
import { ToastHost } from './components/ToastHost'
import { applyBackgroundFromSettings } from './lib/personalization'
import { applyThemeFromSettings } from './lib/theme'
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

/** Sidebar İTME (push) davranışı: `repeat(auto-fill|auto-fit, …)` grid'lerinde kolon
 * sayısı kapsayıcı genişliğine bağlıdır; içerik 168px daralınca eşik geçilir ve ızgara
 * hareketin ORTASINDA yeniden akar (ölçüm: tek karede kart genişliğinde 98-99px sıçrama
 * + kart satır değiştirir; bkz. raporlar/sidebar-itme.md). Geçiş boyunca kolon sayısı
 * hedef değerde sabitlenir → yeniden akış jest ANINDA (t=0) olur; hareket boyunca ızgara
 * kapsayıcıyı izler (1fr), kartlar kesintisiz boyutlanır. Sabit kolonlu grid'ler
 * (home-kpis, secondary-grid, settings-layout…) zaten kesintisiz → kapsam dışı. */
const ITME_GRID_SECICI = '.course-grid, .chapter-grid, .glass-grid, .term-grid, .skeleton-grid'

/** Hedef kolon sayısını ölçer ve grid'leri o sayıda sabitler; sabitlemeyi bırakan
 * fonksiyon döner.
 *
 * Ölçüm: `.app-main` padding'i GEÇİCİ olarak hedef sidebar genişliğine alınır (inline
 * override, animasyonlu `--sidebar-w` değişkenine dokunulmaz → koşan bir geçiş
 * kesilmez), kolon sayıları okunur, inline stil geri alınır. Okuma+yazma aynı görevde
 * olduğu için ara durum ekrana boyanmaz. */
function itmeGridleriniSabitle(hedefSidebar: string): () => void {
  const ana = document.querySelector<HTMLElement>('.app-main')
  const gridler = Array.from(document.querySelectorAll<HTMLElement>(ITME_GRID_SECICI))
  if (!ana || !gridler.length) return () => undefined
  const eskiStil = ana.getAttribute('style')
  ana.style.paddingLeft = hedefSidebar
  const kolonlar = gridler.map((g) => getComputedStyle(g).gridTemplateColumns.split(' ').length)
  if (eskiStil === null) ana.removeAttribute('style')
  else ana.setAttribute('style', eskiStil)
  gridler.forEach((grid, index) => {
    if (kolonlar[index] > 1) grid.style.gridTemplateColumns = `repeat(${kolonlar[index]}, minmax(0, 1fr))`
  })
  return () => {
    for (const grid of gridler) grid.style.removeProperty('grid-template-columns')
  }
}

export default function App() {
  const loading = useAuthStore((s) => s.loading)
  const saasMode = useAuthStore((s) => s.saasMode)
  const session = useAuthStore((s) => s.session)
  const init = useAuthStore((s) => s.init)
  const workspaceFullscreen = useShellStore((s) => s.workspaceFullscreen)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const itmeSabitlemeyiBirakRef = useRef<(() => void) | null>(null)

  /** Sidebar jest anında grid kolon sayısını sabitler; geçiş bitince (animasyonlu
   * genişlik HEDEF değere ulaşınca) bırakır. Bırakma ölçütü duvar saati DEĞİL,
   * animasyonun kendisi: kare başına tek okuma; reduced-motion (1ms) ve yavaşlatılmış/
   * kesintiye uğramış geçişlerde de doğru çalışır, sabitleme asılı kalmaz. */
  const itmeBaslat = (acilacak: boolean) => {
    itmeSabitlemeyiBirakRef.current?.()
    itmeSabitlemeyiBirakRef.current = null
    const birakSabitleme = itmeGridleriniSabitle(acilacak ? 'var(--sidebar-expanded)' : 'var(--sidebar-collapsed)')
    const kabuk = document.querySelector<HTMLElement>('.stuhub-app')
    if (!kabuk) { birakSabitleme(); return }
    const hedef = parseFloat(getComputedStyle(kabuk).getPropertyValue(acilacak ? '--sidebar-expanded' : '--sidebar-collapsed'))
    let kare = 0
    const bitir = () => {
      cancelAnimationFrame(kare)
      birakSabitleme()
      if (itmeSabitlemeyiBirakRef.current === bitir) itmeSabitlemeyiBirakRef.current = null
    }
    const kontrol = () => {
      const suanki = parseFloat(getComputedStyle(kabuk).getPropertyValue('--sidebar-w'))
      if (Number.isFinite(suanki) && Math.abs(suanki - hedef) < 0.5) bitir()
      else kare = requestAnimationFrame(kontrol)
    }
    kare = requestAnimationFrame(kontrol)
    itmeSabitlemeyiBirakRef.current = bitir
  }

  // Kapanışta (çıkış/rota yeniden kurulumu) sabitleme asılı kalmasın.
  useEffect(() => () => { itmeSabitlemeyiBirakRef.current?.(); itmeSabitlemeyiBirakRef.current = null }, [])

  // Route choreography (P4): rota değişince içerik alanına rise-in replay.
  // Sınıf React state'i ile kontrol edilir — imperative class ekleme Suspense
  // re-render'ları tarafından ezilir. State-based toggle iki commit arasında
  // sınıfı gerçekten değiştirir → animasyon güvenle yeniden başlar.
  // Sekme (görünüm) değişimi de AYNI koreografiyi tetikler: `?view=` geçişinde
  // location.pathname sabit kaldığı için eski bağımlılık animasyonu kaçırıyor,
  // içerik animasyonsuz takas ediliyordu (ölçüm: yalnızca height 10 ms).
  // location.key her gezinmede (pathname VEYA search değişimi) değişir →
  // rota ve sekme geçişi tek mekanizma, tek süre/egri.
  // (Tüm hooks early return'lerden ÖNCE — rules-of-hooks.)
  const location = useLocation()
  const [routeAnim, setRouteAnim] = useState(false)
  useEffect(() => {
    setRouteAnim(false)
    const raf = requestAnimationFrame(() => setRouteAnim(true))
    const t = setTimeout(() => setRouteAnim(false), 600)
    return () => { cancelAnimationFrame(raf); clearTimeout(t) }
  }, [location.key])

  useEffect(() => { void init() }, [init])

  // Sunucu tercihleri (tema/arka plan) KİMLİK ister: token yerleşmeden çağrılırsa
  // 401 döner (konsol hatası; ölçüm 2026-09-17: her tam yüklemede 2×401
  // `/api/settings` → sonra reaktif refresh ile 200). Bu yüzden çağrı auth oturumu
  // hazır olana kadar bekler; SaaS modda oturum yokken (giriş ekranı) hiç yapılmaz.
  // Yerel modda kimlik gerekmez, `saasMode` false olduğu için her zaman çalışır.
  // İlk boya zaten index.html'deki yerel aynadan boyanır (bu çağrı onu doğrular).
  // Bağımlılık oturum NESNESİ değil varlığıdır: token yenilemesi (yeni nesne) boşuna
  // yeniden yükleme tetiklemesin.
  const loggedIn = session !== null
  useEffect(() => {
    if (loading || (saasMode && !loggedIn)) return
    void applyThemeFromSettings()
    void applyBackgroundFromSettings()
  }, [loading, saasMode, loggedIn])

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
    <div className={`stuhub-app ${sidebarOpen ? 'stuhub-app--sidebar-open' : ''}`}>
      <CursorRing />
      {/* Otomatik çalışma süresi takibi — bilinçli olarak bileşen sınırında
          (App'in hook listesi bu sayede sabit kalır; bkz. bileşen docstring'i). */}
      <StudyTimeTracker />
      <Sidebar
        open={sidebarOpen}
        onHoverOpen={(value) => {
          // Hover yalnızca desktop'ta (md+) sidebar açar/kapar; mobil off-canvas kalır.
          if (window.matchMedia('(min-width: 768px)').matches) {
            itmeBaslat(value)
            setSidebarOpen(value)
          }
        }}
        onCloseMobile={() => setSidebarOpen(false)}
      />
      <div
        className={`app-main ${workspaceFullscreen ? 'app-main--workspace-fullscreen' : ''}`}
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
