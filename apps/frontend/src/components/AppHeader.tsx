import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useTourController } from '../tour/useTourController'
import { ArrowLeft, Bell, CircleHelp, List, Maximize2, Minimize2 } from 'lucide-react'

/**
 * App Header — kanonik sıra (yönerge §15):
 *   Hamburger → Search (merkez, geniş) → ? → Notification → Browser Fullscreen
 * Profil burada DEĞİLDİR — sidebar'ın alt utility alanındadır (yönerge §7).
 * Search kompakt bir buton değil, header'ın merkez alanını dolduran responsive
 * bir alandır (yönerge §16); tıklanınca merkezi komut paleti açılır.
 */
export function AppHeader({ onMenu }: { onMenu?: () => void }) {
  const location = useLocation()
  const navigate = useNavigate()
  const tour = useTourController()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    const onFullscreen = () => setFullscreen(document.fullscreenElement != null)
    document.addEventListener('fullscreenchange', onFullscreen)
    return () => document.removeEventListener('fullscreenchange', onFullscreen)
  }, [])

  // Bildirim popover'ı dışına tıklanınca kapansın.
  useEffect(() => {
    if (!notificationsOpen) return
    const onPointerDown = (event: MouseEvent) => {
      if (!(event.target as HTMLElement).closest('[data-notifications-root]')) setNotificationsOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [notificationsOpen])

  const currentLayer = location.pathname.startsWith('/dersler/')
    ? location.pathname.includes('/defter/')
      ? 'chapter'
      : 'course'
    : location.pathname.startsWith('/donemler/')
      ? 'term'
      : 'global'

  // Sıkıntı #5 (güncellendi): geri dön — kullanıcı kararı: buton GERÇEK önceki sayfaya
  // dönmeli (history.back), katman hedefine DEĞİL. Geçmiş boşsa (yeni sekme/derin
  // bağlantı) katman bazlı hedefe düşer. `navigate(-1)` güvenli: aynı sekmede SPA
  // geçmişi kalır, A→B→A döngüsüne girmez çünkü hedef her zaman kullanıcının
  // geldiği sayfadır.
  const canGoBack = currentLayer !== 'global'
  const fallbackTarget = (() => {
    const courseMatch = location.pathname.match(/^\/dersler\/(\d+)/)
    const chapterMatch = location.pathname.match(/^\/dersler\/(\d+)\/defter\/(\d+)/)
    if (currentLayer === 'chapter' && chapterMatch) return `/dersler/${chapterMatch[1]}`
    if (currentLayer === 'course' && courseMatch) {
      // Dersin dönemini route'tan bilemeyiz — ders listesi güvenli üst bağlamdır.
      return '/donemler'
    }
    if (currentLayer === 'term') return '/donemler'
    return '/'
  })()

  return (
    <header className="app-header" aria-label="Uygulama üst çubuğu">
      <div className="app-header__left">
        {/* Mobil: sidebar hover ile açılamaz — hamburger yalnızca mobilde */}
        {onMenu && (
          <button
            type="button"
            className="icon-btn md:hidden"
            aria-label="Menüyü aç"
            title="Menüyü aç"
            data-tour-id="sidebar-toggle"
            onClick={onMenu}
          >
            <List size={19} aria-hidden="true" />
          </button>
        )}
        {canGoBack && (
          <button
            type="button"
            className="icon-btn"
            aria-label="Geri dön"
            title="Geri dön"
            onClick={() => {
              // SPA geçmişi varsa gerçek önceki sayfa; yoksa katman hedefi.
              if (window.history.state && window.history.state.idx > 0) navigate(-1)
              else navigate(fallbackTarget)
            }}
          >
            <ArrowLeft size={19} aria-hidden="true" />
          </button>
        )}
      </div>

      {/* Marka: logo + wordmark header'ın geometrik merkezinde (tasarım geri bildirimi 2026-09-16) */}
      <Link to="/" className="app-header__brand" aria-label="StuHub ana sayfa">
        <img src="/brand/stuhub-logo.png" alt="StuHub" className="brand-mark" />
        <span className="brand-wordmark">StuHub</span>
      </Link>

      <div className="app-header__right">
        <button
          type="button"
          className="icon-btn"
          aria-label={`${currentLayer} katmanı için rehberli turu başlat`}
          title="Rehberli tur (?)"
          data-tour-id="help-button"
          onClick={tour.controller.start}
        >
          <CircleHelp size={18} aria-hidden="true" />
        </button>

        <div className="relative" data-notifications-root>
          <button
            type="button"
            className="icon-btn"
            aria-label="Bildirimler"
            title="Bildirimler"
            aria-expanded={notificationsOpen}
            data-tour-id="notification-button"
            onClick={() => setNotificationsOpen((value) => !value)}
          >
            <Bell size={18} aria-hidden="true" />
          </button>
          {notificationsOpen && (
            <div className="popover-panel right-0 top-[calc(100%+10px)] w-[min(360px,calc(100vw-32px))]">
              <div className="popover-panel__heading">Bildirimler</div>
              <div className="empty-inline">
                <Bell size={17} aria-hidden="true" />
                <span>Şimdilik yeni bir bildirimin yok.</span>
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          className="icon-btn"
          aria-label={fullscreen ? 'Tarayıcı tam ekranından çık' : 'Tarayıcı tam ekranı'}
          title={fullscreen ? 'Tam ekrandan çık' : 'Tarayıcı tam ekranı (F11 benzeri)'}
          data-tour-id="browser-fullscreen-button"
          onClick={async () => {
            try {
              if (document.fullscreenElement) await document.exitFullscreen()
              else await document.documentElement.requestFullscreen()
            } catch {
              // Tarayıcı izni/desteği yoksa shell'in geri kalanını bloklamayalım.
            }
          }}
        >
          {fullscreen ? <Minimize2 size={18} aria-hidden="true" /> : <Maximize2 size={18} aria-hidden="true" />}
        </button>
      </div>
      {tour.overlay}
    </header>
  )
}
