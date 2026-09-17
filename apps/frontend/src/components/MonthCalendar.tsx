import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import {
  createCalendarEvent,
  deleteCalendarEvent,
  listCalendarEvents,
  type CalendarEvent,
} from '../api/calendarEvents'
import { coursesApi, type Course } from '../api/courses'
import { termsApi } from '../api/terms'
import { LoaderCircle, Plus, Trash2, X } from 'lucide-react'

/** Ay görünümü hücre grid'i — Pazartesi başlangıçlı (TR). */
const WEEKDAY_LABELS = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']

/** Etkinlik türü renk dili — hücre noktası, popover satırı ve alt lejant aynı
 * eşlemeyi kullanır (tek kaynak): exam=warning, assignment=accent,
 * project=text-secondary + halka, custom=text-secondary. */
const KIND_DOT: Record<CalendarEvent['kind'], string> = {
  exam: 'bg-stuhub-warning',
  assignment: 'bg-stuhub-accent',
  project: 'bg-stuhub-text-secondary ring-1 ring-stuhub-text-secondary',
  custom: 'bg-stuhub-text-secondary',
}

const KIND_LABEL: Record<CalendarEvent['kind'], string> = {
  exam: 'Sınav',
  assignment: 'Ödev',
  project: 'Proje',
  custom: 'Kişisel not',
}

/** Lejant sırası (tür yoğunluğuna göre: sınav → ödev → proje → not). */
const KIND_ORDER: CalendarEvent['kind'][] = ['exam', 'assignment', 'project', 'custom']

function toISODate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** Hücre ile popover arası boşluk (eski `mt-1`) ve viewport kenar payı. */
const POPOVER_GAP = 4
const POPOVER_MARGIN = 8

/**
 * Hücrenin ALTINA, viewport dışına taşmayacak konumu hesaplar (rect tabanlı —
 * portal'da sınıf tabanlı hizalama yok). Yatay hizalama hücre rect'inden
 * türetilir: sol/sağ üçte birlikte hücrenin ilgili kenarına yaslanır, ortada
 * merkezlenir; sonra viewport'a clamp edilir. Alta sığmıyorsa (son satır) üste
 * döner — hiçbir durumda kenardan taşmaz.
 */
function placePopover(rect: DOMRect, width: number, height: number): { top: number; left: number } {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const center = rect.left + rect.width / 2
  let left = center - width / 2
  if (center < vw / 3) left = rect.left
  else if (center > (vw * 2) / 3) left = rect.right - width
  left = Math.min(Math.max(left, POPOVER_MARGIN), Math.max(POPOVER_MARGIN, vw - width - POPOVER_MARGIN))
  let top = rect.bottom + POPOVER_GAP
  if (top + height > vh - POPOVER_MARGIN) top = Math.max(POPOVER_MARGIN, rect.top - height - POPOVER_GAP)
  return { top, left }
}

interface MonthCalendarProps {
  /** Ders seçici için opsiyonel ders listesi; verilmezse boş yüklenir. */
  courses?: Course[]
}

/**
 * Aylık takvim (sıkıntı #4) — glass tasarım dili:
 * - Etkinlikli günler parlak (accent luminosity) + nokta belirteci
 * - Hover'da günün etkinlikleri popover
 * - Güne tıklayınca sınav/ödev notu ekleme (sınavlar exams'tan salt okunur)
 */
export function MonthCalendar({ courses: coursesProp }: MonthCalendarProps) {
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1),
  )
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [hoveredDate, setHoveredDate] = useState<string | null>(null)
  const [addingDate, setAddingDate] = useState<string | null>(null)
  const [newTitle, setNewTitle] = useState('')
  const [newKind, setNewKind] = useState<'assignment' | 'custom' | 'exam' | 'project'>('assignment')
  const [newCourseId, setNewCourseId] = useState<number | ''>('')
  // Kullanıcı tanımlı etiketler (sıkıntı: tag eklenemiyordu) — virgülle ayrılmış serbest metin.
  const [newTags, setNewTags] = useState('')
  // Grid klavye navigasyonu (P4 a11y): roving tabindex + ok tuşları —
  // role=grid sözleşmesi (WCAG 2.1.1). 7 sütun = hafta; ↑↓ ±7 gün, ←→ ±1 gün,
  // Home/End hafta başı/sonu. Grid container'a aria-live ile ay duyurulur.
  const gridRef = useRef<HTMLDivElement>(null)
  const [focusedDay, setFocusedDay] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [courses, setCourses] = useState<Course[]>(coursesProp ?? [])
  // Portal popover: DOM düğümü + konumu; anchor hücre ref'i köprü kontrolleri için.
  const popoverRef = useRef<HTMLDivElement>(null)
  const popoverAnchorRef = useRef<HTMLElement | null>(null)
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number } | null>(null)

  // Ay aralığı (başlangıç Pazartesi'ye, bitiş Pazar'a genişletilmiş)
  const monthRange = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1)
    const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0)
    const startOffset = (first.getDay() + 6) % 7
    const gridStart = new Date(first)
    gridStart.setDate(first.getDate() - startOffset)
    const endOffset = (7 - ((last.getDay() + 6) % 7 + 1)) % 7
    const gridEnd = new Date(last)
    gridEnd.setDate(last.getDate() + endOffset)
    return { gridStart, gridEnd, daysInGrid: Math.round((gridEnd.getTime() - gridStart.getTime()) / 86_400_000) + 1 }
  }, [cursor])

  useEffect(() => {
    const start = toISODate(monthRange.gridStart)
    const end = toISODate(monthRange.gridEnd)
    let cancelled = false
    setLoading(true)
    void listCalendarEvents(start, end)
      .then((items) => {
        if (!cancelled) setEvents(items)
      })
      .catch(() => {
        if (!cancelled) setEvents([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [monthRange])

  useEffect(() => {
    if (coursesProp || courses.length > 0) return
    let cancelled = false
    void termsApi.list()
      .then((terms) =>
        Promise.all(terms.map((term) => coursesApi.listByTerm(term.id).catch(() => [] as Course[]))),
      )
      .then((grouped) => {
        if (!cancelled) setCourses(grouped.flat())
      })
      .catch(() => undefined)
    return () => { cancelled = true }
  }, [coursesProp, courses.length])

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>()
    events.forEach((event) => {
      const list = map.get(event.event_date) ?? []
      list.push(event)
      map.set(event.event_date, list)
    })
    return map
  }, [events])

  /** course_id → ders adı; popover satırında tür ile birlikte gösterilir. */
  const courseNames = useMemo(
    () => new Map(courses.map((course) => [course.id, course.name])),
    [courses],
  )

  const days = useMemo(() => {
    const list: Date[] = []
    const d = new Date(monthRange.gridStart)
    for (let i = 0; i < monthRange.daysInGrid; i += 1) {
      list.push(new Date(d))
      d.setDate(d.getDate() + 1)
    }
    return list
  }, [monthRange])

  /** Popover yalnızca etkinlikli günde açılır (koşul değişmedi) — portal
   * içeriği bu tarihe göre render edilir. */
  const openDate = hoveredDate && (eventsByDate.get(hoveredDate)?.length ?? 0) > 0 ? hoveredDate : null
  const openEvents = openDate ? eventsByDate.get(openDate) ?? [] : []

  /**
   * Ay değişimi popover'ı kapatır: komşu ay günleri grid'de kaldığı için anchor
   * hücre yeni ayda da bulunuyor ve popover görünürlüğü süren, artık ay dışı
   * (soluk) hücreye yapışıyordu. Tek noktadan sıfırlama cursor'ı taşıyan bütün
   * kaynakları kapsar (önceki/sonraki ay düğmeleri, klavye navigasyonu).
   */
  useEffect(() => {
    setHoveredDate(null)
  }, [cursor])

  /**
   * Portal konumu: anchor hücre getBoundingClientRect()'inden hesaplanır
   * (hücre stack'i dışında, fixed). Hover/ay değişiminde yeniden ölçülür;
   * scroll (yakalama fazı: iç kaydırma kapları dahil) ve resize'da tazelenir.
   * Hücre grid'den kalkmışsa (ay değişti) popover kapanır.
   */
  useLayoutEffect(() => {
    if (!openDate) return
    const anchor = gridRef.current?.querySelector<HTMLElement>(`[data-iso="${openDate}"]`)
    if (!anchor) {
      setHoveredDate(null)
      return
    }
    popoverAnchorRef.current = anchor
    const update = () => {
      const el = popoverRef.current
      if (!el) return
      const next = placePopover(anchor.getBoundingClientRect(), el.offsetWidth, el.offsetHeight)
      // Konum aynıysa state'i değiştirme: scroll boyunca gereksiz render olmasın.
      setPopoverPos((prev) => (prev && prev.top === next.top && prev.left === next.left ? prev : next))
    }
    update()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
      popoverAnchorRef.current = null
    }
  }, [openDate])

  const todayISO = toISODate(today)

  const handleCreate = async () => {
    // Enter hızlı çift basışta ikinci POST'u engelle (creating guard'i yoktu —
    // idempotent uç değil, mükerrer etkinlik oluşurdu).
    if (!addingDate || !newTitle.trim() || creating) return
    setCreating(true)
    setError('')
    try {
      const tags = newTags.split(',').map((t) => t.trim()).filter(Boolean).slice(0, 6)
      const created = await createCalendarEvent({
        event_date: addingDate,
        kind: newKind,
        title: newTitle.trim(),
        course_id: newCourseId === '' ? null : Number(newCourseId),
        tags,
      })
      if (!created) {
        setError('Etkinlik eklenemedi. Lütfen tekrar deneyin.')
        return
      }
      setEvents((prev) =>
        [...prev, created].sort((a, b) => a.event_date.localeCompare(b.event_date)),
      )
      setNewTitle('')
      setNewTags('')
      setAddingDate(null)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (event: CalendarEvent) => {
    if (event.source !== 'user') return
    const ok = await deleteCalendarEvent(event.id)
    if (ok) {
      setEvents((prev) => prev.filter((e) => e.id !== event.id))
    } else {
      // Sessiz başarısızlık yerine görünür geri bildirim (sıkıntı: silent failure).
      setError('Etkinlik silinemedi. Lütfen tekrar deneyin.')
    }
  }

  const monthLabel = cursor.toLocaleDateString('tr-TR', { month: 'long', year: 'numeric' })

  /**
   * Portal köprüsü: popover artık hücrenin DOM çocuğu değil, bu yüzden imleç
   * hücreden popover'a geçerken hücrede mouseleave/blur tetiklenir. Hedef
   * popover içindeyse kapatma — aksi halde silme/kapat düğmelerine erişilemezdi.
   */
  const closeUnlessInPopover = (related: EventTarget | null, iso: string) => {
    if (related instanceof Node && popoverRef.current?.contains(related)) return
    setHoveredDate((current) => (current === iso ? null : current))
  }

  /** Ters yön: popover'dan çıkış hücreye dönüyorsa da kapatma (çift yönlü köprü). */
  const closeIfLeavingPopover = (related: EventTarget | null) => {
    if (related instanceof Node && (popoverRef.current?.contains(related) || popoverAnchorRef.current?.contains(related))) return
    setHoveredDate(null)
  }

  return (
    <div className="glass-panel p-5" role="group" aria-label="Aylık takvim">
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="icon-btn"
          aria-label="Önceki ay"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
        >
          ‹
        </button>
        <h2 className="text-lg font-semibold first-letter:uppercase">{monthLabel}</h2>
        <button
          type="button"
          className="icon-btn"
          aria-label="Sonraki ay"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
        >
          ›
        </button>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-1.5" aria-hidden="true">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="py-1 text-center text-xs font-medium text-stuhub-text-muted">
            {label}
          </div>
        ))}
      </div>

      <div
        ref={gridRef}
        className="grid grid-cols-7 gap-1.5"
        role="grid"
        aria-label={`${monthLabel} takvimi`}
        onKeyDown={(e) => {
          // Ok tuşu grid navigasyonu (roving tabindex). Hedef gün başka haftadaysa
          // cursor'ı da taşı — ay değişimi hover/popover akışıyla aynı kalır.
          const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']
          if (!keys.includes(e.key)) return
          const cells = [...gridRef.current?.querySelectorAll<HTMLElement>('[role="gridcell"]') ?? []]
          const isoList = cells.map((c) => c.getAttribute('data-iso'))
          const cur = hoveredDate ?? isoList.find(Boolean) ?? null
          if (!cur) return
          const idx = isoList.indexOf(cur)
          if (idx < 0) return
          e.preventDefault()
          let next = idx
          if (e.key === 'ArrowLeft') next = idx - 1
          if (e.key === 'ArrowRight') next = idx + 1
          if (e.key === 'ArrowUp') next = idx - 7
          if (e.key === 'ArrowDown') next = idx + 7
          if (e.key === 'Home') next = idx - (idx % 7)
          if (e.key === 'End') next = idx - (idx % 7) + 6
          const target = cells[next]
          if (!target) return
          const iso = target.getAttribute('data-iso')
          if (iso) { setHoveredDate(iso); setFocusedDay(iso); requestAnimationFrame(() => target.querySelector<HTMLElement>('button')?.focus()) }
        }}
      >
        {days.map((date) => {
          const iso = toISODate(date)
          const inMonth = date.getMonth() === cursor.getMonth()
          const isToday = iso === todayISO
          const dayEvents = eventsByDate.get(iso) ?? []
          const hasEvent = dayEvents.length > 0
          return (
            <div
              key={iso}
              role="gridcell"
              data-iso={iso}
              aria-label={`${date.toLocaleDateString('tr-TR')}${hasEvent ? `, ${dayEvents.length} etkinlik` : ''}`}
              className={`relative flex min-h-16 flex-col rounded-control border p-1.5 text-left transition-colors duration-[var(--duration-micro)] ${addingDate === iso ? 'cal-cell--adding' : ''} ${
                hasEvent
                  ? 'border-stuhub-accent/40 bg-stuhub-accent-glass shadow-[0_0_12px_-4px_rgba(255,255,255,0.35)] hover:bg-stuhub-glass-1-hover'
                  : 'border-stuhub-border bg-stuhub-glass-1 hover:bg-stuhub-glass-2-hover'
              } ${inMonth ? '' : 'opacity-40'}`}
              onMouseEnter={() => setHoveredDate(iso)}
              onMouseLeave={(e) => closeUnlessInPopover(e.relatedTarget, iso)}
              /* Klavye eşdeğerliliği: hover-only popover Screen reader/klavye
               * kullanıcısına etkinlikleri göstermezdi — odaklanınca da açılır. */
              onFocusCapture={() => setHoveredDate(iso)}
              onBlurCapture={(e) => closeUnlessInPopover(e.relatedTarget, iso)}
            >
              <button
                type="button"
                onClick={() => { setAddingDate(iso); setNewKind('assignment'); setNewTitle(''); setNewTags('') }}
                tabIndex={focusedDay === null ? (iso === todayISO ? 0 : hoveredDate === iso ? 0 : -1) : focusedDay === iso ? 0 : -1}
                className="flex flex-1 flex-col items-stretch text-left"
                aria-label={`${date.toLocaleDateString('tr-TR')} gününe not ekle`}
              >
                <span
                  className={`text-xs font-medium ${isToday ? 'flex h-5 w-5 items-center justify-center rounded-pill bg-stuhub-accent text-stuhub-on-accent' : ''}`}
                >
                  {date.getDate()}
                </span>
                {/* Nokta alanı HER hücrede rezerve edilir (h-2.5): etkinlikli ve
                 * etkinliksiz hücreler aynı dikey ritmi korur, noktalar 8px. */}
                <span className="mt-auto flex h-2.5 items-center gap-1" aria-hidden="true">
                  {dayEvents.slice(0, 3).map((event) => (
                    <span key={event.id} className={`h-2 w-2 rounded-pill ${KIND_DOT[event.kind]}`} />
                  ))}
                  {dayEvents.length > 3 && (
                    <span className="text-[10px] font-medium leading-none text-stuhub-text-secondary">
                      +{dayEvents.length - 3}
                    </span>
                  )}
                </span>
              </button>
            </div>
          )
        })}
      </div>

      {/* Hover popover — günün etkinlikleri. createPortal ile document.body'ye
       * taşınır: hücre stack'inden bağımsız (fixed) ve hücreyi örtmez — anchor
       * hücrenin ALTINA (rect.bottom + 4px) konumlanır. Konum rect tabanlı;
       * yatay hizalama viewport'a clamp'li, son satırda alta sığmazsa üste
       * döner (placePopover). Opak zemin + yüksek z korunur; içerik gösterim,
       * odak hücrede kalır (kapatma hover-out/blur akışı aynı). */}
      {openDate &&
        createPortal(
          <div
            ref={popoverRef}
            style={{
              top: popoverPos?.top ?? 0,
              left: popoverPos?.left ?? 0,
              // Konum ilk ölçüme kadar hesaplanmış sayılmaz — 0,0'da sıçramasın.
              visibility: popoverPos ? undefined : 'hidden',
            }}
            className="fixed z-50 w-56 rounded-control border border-stuhub-border bg-[var(--stuhub-panel-bg)] p-3 shadow-[0_12px_32px_rgba(0,0,0,0.75)]"
            role="status"
            onMouseLeave={(e) => closeIfLeavingPopover(e.relatedTarget)}
            onBlurCapture={(e) => closeIfLeavingPopover(e.relatedTarget)}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="eyebrow text-stuhub-text-secondary">ETKİNLİKLER</p>
              <button
                type="button"
                className="icon-btn h-8 w-8 shrink-0"
                aria-label="Kapat"
                onClick={() => setHoveredDate(null)}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
            <ul className="mt-2 space-y-2">
              {openEvents.map((event) => (
                <li key={`${event.source}-${event.id}`} className="flex items-start justify-between gap-2">
                  <span className="min-w-0 text-[13px] leading-snug text-stuhub-text">
                    <span
                      className={`mr-1.5 inline-block h-2 w-2 shrink-0 rounded-pill align-middle ${KIND_DOT[event.kind]}`}
                      aria-hidden="true"
                    />
                    {/* D9: uzun ders adı popover satırını taşıyordu — truncate
                     * yerine sarılır (2 satıra kadar), hiç kırpılmaz. */}
                    <span className="break-words">{event.title}</span>
                    {/* Tür + ders: ikincil ama okunur kontrastta (12px). */}
                    <span className="mt-0.5 block text-xs text-stuhub-text-secondary">
                      {[KIND_LABEL[event.kind], courseNames.get(event.course_id ?? -1)]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                    {event.tags.length > 0 && (
                      <span className="mt-1 flex flex-wrap gap-1">
                        {event.tags.map((tag) => (
                          <span key={tag} className="glass-panel-subtle rounded-pill px-1.5 py-0.5 text-[10px] text-stuhub-text-secondary">
                            {tag}
                          </span>
                        ))}
                      </span>
                    )}
                  </span>
                  {event.source === 'user' && (
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger shrink-0"
                      aria-label={`${event.title} etkinliğini sil`}
                      onClick={() => void handleDelete(event)}
                    >
                      <Trash2 size={11} aria-hidden="true" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}

      {loading && (
        <p className="mt-3 flex items-center gap-2 text-xs text-stuhub-text-muted" role="status">
          <LoaderCircle size={13} className="animate-spin" /> Etkinlikler yükleniyor…
        </p>
      )}

      {/* Not ekleme formu */}
      {addingDate && (
        <div className="glass-panel-subtle mt-4 p-4" role="dialog" aria-modal="false" aria-label="Etkinlik ekle">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">
              {new Date(`${addingDate}T12:00:00`).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })} — not ekle
            </p>
            <button type="button" className="icon-btn" aria-label="Vazgeç" onClick={() => setAddingDate(null)}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <select
              value={newKind}
              onChange={(e) => setNewKind(e.target.value as 'assignment' | 'custom' | 'exam' | 'project')}
              className="rounded-control border border-stuhub-border bg-stuhub-glass-2 px-2 py-1.5 text-sm"
              aria-label="Etkinlik türü"
            >
              <option value="assignment">Ödev</option>
              <option value="exam">Sınav</option>
              <option value="project">Proje</option>
              <option value="custom">Kişisel not</option>
            </select>
            <select
              value={newCourseId}
              onChange={(e) => setNewCourseId(e.target.value === '' ? '' : Number(e.target.value))}
              className="rounded-control border border-stuhub-border bg-stuhub-glass-2 px-2 py-1.5 text-sm"
              aria-label="Ders (opsiyonel)"
            >
              <option value="">Ders seç…</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>{course.name}</option>
              ))}
            </select>
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
              placeholder="Başlık…"
              autoFocus
              className="min-w-40 flex-1 rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-1.5 text-sm outline-none focus:border-stuhub-accent"
              aria-label="Etkinlik başlığı"
            />
            <input
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
              placeholder="Etiketler (virgülle: vize, grup çalışması…)"
              className="min-w-40 flex-1 rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-1.5 text-sm outline-none focus:border-stuhub-accent"
              aria-label="Etiketler — virgülle ayır"
            />
            <button type="button" className="btn-primary" disabled={creating || !newTitle.trim()} onClick={() => void handleCreate()}>
              {creating ? <LoaderCircle size={15} className="animate-spin" aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}
              Ekle
            </button>
          </div>
          {error && <p role="alert" className="mt-2 text-sm text-stuhub-error">{error}</p>}
        </div>
      )}

      <p className="mt-4 flex flex-wrap items-center gap-4 text-xs text-stuhub-text-muted">
        {KIND_ORDER.map((kind) => (
          <span key={kind} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-pill ${KIND_DOT[kind]}`} aria-hidden="true" /> {KIND_LABEL[kind]}
          </span>
        ))}
      </p>
    </div>
  )
}
