import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { supabaseClient } from '../lib/supabaseClient'
import { useAuthStore } from '../stores/authStore'
import { usePaletteStore } from '../stores/paletteStore'
import { chaptersApi, type Chapter } from '../api/chapters'
import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import {
  BookOpen, Calendar, ChevronRight, ClipboardCheck, Crosshair, FileText,
  House, Layers, ListChecks, NotebookPen, Search, Settings, Sparkle, Trophy, X,
} from 'lucide-react'

interface SidebarProps {
  open: boolean
  /** Desktop'ta hover ile aç/kapa (App matchMedia ile mobile'da yoksayar). */
  onHoverOpen?: (open: boolean) => void
  onCloseMobile?: () => void
}

type NavItem = { label: string; to?: string; icon: typeof House; children?: NavItem[]; tourId?: string }

/** Sıkıntı #9: item active'i path + ?view= paramına bakarak belirler — böylece
 * aynı chapter'da Notlar/Quiz/Flashcard sekmeleri birbirinden ayrışır ve her
 * layer'da yalnızca bulunulan sekme vurgulanır (global referans davranışı). */
function itemActive(pathname: string, search: string, to: string): boolean {
  const [toPath, toQuery] = to.split('?')
  if (pathname !== toPath && !pathname.startsWith(`${toPath}/`)) return false
  const currentView = new URLSearchParams(search).get('view')
  const targetView = new URLSearchParams(toQuery ?? '').get('view')
  // Hedefte view yoksa (Genel/dashboard) yalnızca URL'de de view yokken aktiftir.
  return (targetView ?? null) === (currentView ?? null)
}

function FeatureButton({ item, collapsed, active, onSelect }: { item: NavItem; collapsed: boolean; active: boolean; onSelect: () => void }) {
  const Icon = item.icon
  const content = (
    <span
      className={`nav-item ${active ? 'nav-item--active' : ''} ${collapsed ? 'nav-item--collapsed' : ''}`}
      data-tour-id={item.tourId}
    >
      <Icon size={18} aria-hidden="true" />
      <span className="nav-item__label">{item.label}</span>
      {item.children && !collapsed && <ChevronRight size={15} className="ml-auto opacity-50" aria-hidden="true" />}
    </span>
  )

  // Daraltılmış sidebar'da tema `.nav-item__label`'ı display:none yapıyor (theme.css);
  // erişilebilir ad yalnızca ikondan gelemediği için (ikonlar aria-hidden) link isimsiz
  // kalıyordu — ad bu yüzden açıkça verilir. Görsel çıktı değişmez.
  if (item.to) return <Link to={item.to} onClick={onSelect} aria-label={item.label}>{content}</Link>
  return <button type="button" onClick={onSelect} className="block w-full text-left" aria-label={item.label}>{content}</button>
}

function initials(name?: string, email?: string): string {
  const source = name?.trim() || email?.trim() || 'StuHub'
  const parts = source.split(/\s+/).filter(Boolean)
  return parts.length > 1 ? `${parts[0][0]}${parts[1][0]}`.toUpperCase() : source.slice(0, 2).toUpperCase()
}

/** Sidebar alt utility/account alanındaki profil kontrolü — glass account card (yönerge §7). */
function SidebarProfile({ onSelect }: { onSelect: () => void }) {
  const user = useAuthStore((s) => s.user)
  const saasMode = useAuthStore((s) => s.saasMode)
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const metadata = user?.user_metadata as Record<string, unknown> | undefined
  const candidate = metadata?.full_name ?? metadata?.name
  const displayName = typeof candidate === 'string' && candidate.trim() ? candidate.trim() : user?.email?.split('@')[0] ?? 'Öğrenci'
  const username = user?.email ? `@${user.email.split('@')[0]}` : '@student'
  const tier = saasMode ? 'FREE · Yükselt' : 'PRO'

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="profile-trigger w-full"
        data-tour-id="profile-trigger"
        aria-label="Hesap ve profil"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="avatar avatar--small">{initials(displayName, user?.email)}</span>
        <span className="nav-item__label min-w-0 truncate text-left">{displayName}</span>
      </button>

      {open && (
        <div className="popover-panel left-0 bottom-[calc(100%+10px)] w-[min(300px,calc(100vw-32px))]">
          <div className="profile-card">
            <div className="profile-card__identity">
              <span className="avatar avatar--large">{initials(displayName, user?.email)}</span>
              <div className="min-w-0">
                <p className="truncate font-semibold">{displayName}</p>
                <p className="truncate text-sm text-stuhub-text-secondary">{username}</p>
              </div>
            </div>
            <div className="profile-tier">{tier}</div>
            <div className="profile-card__links">
              <Link to="/ayarlar" onClick={() => { setOpen(false); onSelect() }} className="list-row">
                Profil / Hesap
              </Link>
              <Link to="/ayarlar" onClick={() => { setOpen(false); onSelect() }} className="list-row">
                Ayarlar
              </Link>
              {saasMode && tier.startsWith('FREE') && (
                <Link to="/paywall" onClick={() => { setOpen(false); onSelect() }} className="list-row list-row--emphasis">
                  Yükselt
                </Link>
              )}
              {saasMode && (
                <button
                  type="button"
                  className="list-row list-row--destructive"
                  onClick={() => {
                    setOpen(false)
                    void supabaseClient?.auth.signOut()
                  }}
                >
                  Çıkış Yap
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function Sidebar({ open, onHoverOpen, onCloseMobile }: SidebarProps) {
  const location = useLocation()
  const openPalette = usePaletteStore((s) => s.toggle)
  const [terms, setTerms] = useState<Term[]>([])
  const [coursesByTerm, setCoursesByTerm] = useState<Record<number, Course[]>>({})
  const [chaptersByCourse, setChaptersByCourse] = useState<Record<number, Chapter[]>>({})
  const courseMatch = location.pathname.match(/^\/dersler\/(\d+)/)
  const chapterMatch = location.pathname.match(/^\/dersler\/(\d+)\/defter\/(\d+)/)
  const currentCourseId = Number(courseMatch?.[1])
  const currentChapterId = Number(chapterMatch?.[2])

  useEffect(() => {
    let cancelled = false
    void termsApi.list().then((items) => {
      if (!cancelled) setTerms(items)
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!currentCourseId) return
    if (chaptersByCourse[currentCourseId]) return
    void chaptersApi.listByCourse(currentCourseId).then((items) => {
      setChaptersByCourse((prev) => ({ ...prev, [currentCourseId]: items }))
    }).catch(() => undefined)
  }, [currentCourseId, chaptersByCourse])

  useEffect(() => {
    if (!terms.length) return
    const missing = terms.filter((term) => !coursesByTerm[term.id]).slice(0, 6)
    if (!missing.length) return
    void Promise.all(missing.map(async (term) => [term.id, await coursesApi.listByTerm(term.id).catch(() => [])] as const))
      .then((entries) => setCoursesByTerm((prev) => ({ ...prev, ...Object.fromEntries(entries) })))
  }, [terms, coursesByTerm])

  const currentTermId = useMemo(() => {
    const match = terms.find((term) => location.pathname.startsWith(`/donemler/${term.id}`))
    if (match) return match.id
    const activeCourse = Object.entries(coursesByTerm).find(([, courses]) => courses.some((course) => course.id === currentCourseId))
    return activeCourse ? Number(activeCourse[0]) : undefined
  }, [terms, coursesByTerm, currentCourseId, location.pathname])

  const currentTerm = terms.find((term) => term.id === currentTermId)

  const globalItems: NavItem[] = [
    { label: 'Ana Sayfa', to: '/', icon: House },
    { label: 'Dönemler', to: '/donemler', icon: ListChecks },
    // Sıkıntı: derslere erişim yalnızca bir dönem seçildiğinde anlamlı —
    // ana layer'da Dersler girdisi kaldırıldı (sadece dönem layer'ında listelenir).
    { label: 'Takvim', to: '/takvim', icon: Calendar },
    { label: 'Sınav Planı', to: '/sinav-plani', icon: Trophy },
    { label: 'Bugün Ne Çalışsam?', to: '/calisma', icon: Crosshair },
  ]

  const termItems: NavItem[] = currentTermId ? [
    { label: currentTerm ? currentTerm.name : 'Dönem Özeti', to: `/donemler/${currentTermId}`, icon: ListChecks },
    { label: 'Dersler', to: `/donemler/${currentTermId}`, icon: BookOpen },
    { label: 'Takvim', to: `/donemler/${currentTermId}?view=calendar`, icon: Calendar },
    { label: 'Sınav Planı', to: `/donemler/${currentTermId}?view=exam-plan`, icon: Trophy },
    { label: 'Bugün Ne Çalışsam?', to: `/donemler/${currentTermId}?view=study-now`, icon: Crosshair },
  ] : []

  const courseBase = `/dersler/${currentCourseId}`
  const courseItems: NavItem[] = currentCourseId ? [
    { label: 'Genel', to: courseBase, icon: House },
    { label: 'Notlar', to: `${courseBase}?view=notes`, icon: FileText, tourId: 'sidebar-course-notes' },
    { label: 'Kaydedilenler', to: `${courseBase}?view=saved`, icon: NotebookPen, tourId: 'sidebar-course-saved' },
    { label: 'Flashcard Practice', to: `${courseBase}?view=flashcards`, icon: Layers, tourId: 'sidebar-course-flashcards' },
    { label: 'Kaydırarak Quiz', to: `${courseBase}?view=swipe-quiz`, icon: Sparkle, tourId: 'sidebar-course-swipe' },
    { label: 'Materyale Sor', to: `${courseBase}?view=material-ask`, icon: Search, tourId: 'sidebar-course-ask' },
    { label: 'Ödev Değerlendir', to: `${courseBase}?view=assignment-evaluation`, icon: ClipboardCheck, tourId: 'sidebar-course-assignments' },
    { label: 'Ödev Taslak Koçu', to: `${courseBase}?view=assignment-draft-coach`, icon: NotebookPen },
  ] : []

  const chapterBase = currentChapterId ? `/dersler/${currentCourseId}/defter/${currentChapterId}` : ''
  const chapterItems: NavItem[] = currentChapterId ? [
    { label: 'Genel', to: chapterBase, icon: House },
    { label: 'Notlar', to: `${chapterBase}?view=notes`, icon: FileText, tourId: 'sidebar-chapter-notes' },
    { label: 'Quiz', to: `${chapterBase}?view=quiz`, icon: ListChecks, tourId: 'sidebar-chapter-quiz' },
    { label: 'Flashcard Practice', to: `${chapterBase}?view=flashcards`, icon: Layers, tourId: 'sidebar-chapter-flashcards' },
    { label: 'Materyale Sor', to: `${chapterBase}?view=material-ask`, icon: Search, tourId: 'sidebar-chapter-ask' },
  ] : []

  const items = currentChapterId ? chapterItems : currentCourseId ? courseItems : currentTermId ? termItems : globalItems

  return (
    <>
      {open && <button type="button" className="sidebar-backdrop md:hidden" aria-label="Menüyü kapat" onClick={onCloseMobile} />}
      <aside
        className={`app-sidebar ${open ? 'app-sidebar--open' : 'app-sidebar--collapsed'}`}
        onMouseEnter={() => onHoverOpen?.(true)}
        onMouseLeave={() => onHoverOpen?.(false)}
      >
        {/* Yalnızca mobil: açık sidebar'da kapatma düğmesi. Desktop'ta hover ile açılır/kapanır. */}
        <div className="app-sidebar__brand md:hidden">
          <button type="button" className="mobile-close icon-btn" aria-label="Menüyü kapat" onClick={onCloseMobile}><X size={18} /></button>
        </div>

        {/* Arama sidebar'a taşındı (tasarım geri bildirimi 2026-09-16) */}
        <div className="app-sidebar__search">
          <button type="button" className="search-control" aria-label="Ders, not ve içeriklerde ara" data-tour-id="global-search" onClick={openPalette}>
            <Search size={17} aria-hidden="true" />
            <span className="search-control__hint">Ders, not, quiz ara…</span>
            <kbd>Ctrl K</kbd>
          </button>
        </div>

        <nav className="app-sidebar__nav" aria-label="Ana gezinme">
          {items.map((item) => {
            const active = item.to ? itemActive(location.pathname, location.search, item.to) : false
            return (
              <div key={item.label} className="sidebar-item-wrap">
                <FeatureButton item={item} collapsed={!open} active={active} onSelect={onCloseMobile ?? (() => undefined)} />
              </div>
            )
          })}
        </nav>

        <div className="app-sidebar__footer">
          <Link
            to="/ayarlar"
            onClick={onCloseMobile}
            title="Ayarlar"
            className={`nav-item ${!open ? 'nav-item--collapsed' : ''} ${itemActive(location.pathname, location.search, '/ayarlar') ? 'nav-item--active' : ''}`}
          >
            <Settings size={18} aria-hidden="true" />
            <span className="nav-item__label">Ayarlar</span>
          </Link>
          <SidebarProfile onSelect={onCloseMobile ?? (() => undefined)} />
        </div>
      </aside>
    </>
  )
}
