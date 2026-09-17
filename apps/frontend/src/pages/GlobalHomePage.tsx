import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import { NextActionCard } from '../components/NextActionCard'
import { getWeeklyStudy, type WeeklyStudy } from '../api/streaks'
import { StreakRing } from '../components/StreakRing'
import { ArrowRight, BookOpen, Calendar, ChartLine, Crosshair, Trophy } from 'lucide-react'

export function GlobalHomePage() {
  const navigate = useNavigate()
  const [terms, setTerms] = useState<Term[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [weeklyStudy, setWeeklyStudy] = useState<WeeklyStudy | null>(null)
  // Layout-shift: haftalık veri gelene kadar grafiğin GERÇEK kutusunu rezerve etmek
  // için "boş" ile "henüz yükleniyor" ayrılır (ikisi de weeklyStudy=null idi).
  const [weeklyHazir, setWeeklyHazir] = useState(false)

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      termsApi.list().then(async (items) => {
        if (cancelled) return
        setTerms(items)
        const entries = await Promise.all(items.map(async (term) => await coursesApi.listByTerm(term.id).catch(() => [])))
        if (!cancelled) setCourses(entries.flat())
      }),
      getWeeklyStudy()
        .then((data) => { if (!cancelled) setWeeklyStudy(data) })
        .catch(() => undefined)
        .finally(() => { if (!cancelled) setWeeklyHazir(true) }),
    ]).catch(() => undefined)
    return () => { cancelled = true }
  }, [])

  // Otomatik süre takibi arka planda 5 dk'lık bloklar yazıyor (sıkıntı #2) —
  // grafik canlı kalsın diye haftalık veri periyodik yenilenir.
  useEffect(() => {
    const id = window.setInterval(() => {
      void getWeeklyStudy()
        .then((data) => setWeeklyStudy(data))
        .catch(() => undefined)
    }, 60_000)
    return () => window.clearInterval(id)
  }, [])

  // "Bugün ne çalışsam?" kartı ilk dersin önerisini gösterir (kartın kendi kuralı).
  const oneriDersi = courses[0]

  return (
    <section className="page-shell">
      <header className="welcome-panel glass-panel anim-rise">
        <div>
          <p className="eyebrow">STUHUB</p>
          <h1 className="page-title">Çalışmaya başlamak için iyi bir an.</h1>
          <p className="page-subtitle">{terms.length} dönem · {courses.length} ders · bugünkü öğrenme durumun burada.</p>
        </div>
        <Link to="/calisma" className="btn-primary">Çalışmaya Başla <ArrowRight size={16} aria-hidden="true" /></Link>
      </header>

      <div className="home-kpis">
        <div className="glass-panel metric-card"><BookOpen size={18} aria-hidden="true" /><span className="eyebrow">DERSLER</span><strong>{courses.length}</strong></div>
        <div className="glass-panel metric-card"><Trophy size={18} aria-hidden="true" /><span className="eyebrow">DÖNEMLER</span><strong>{terms.length}</strong></div>
        <div className="glass-panel metric-card"><Crosshair size={18} aria-hidden="true" /><span className="eyebrow">SONRAKİ ADIM</span><span>Bugün Ne Çalışsam?</span></div>
      </div>

      <div className="home-grid">
        <div className="glass-panel feature-card">
          <div className="feature-card__top"><Crosshair size={20} aria-hidden="true" /><span>Bugün Ne Çalışsam?</span></div>
          {oneriDersi ? (
            <NextActionCard
              courseId={oneriDersi.id}
              // Kart setleri için ayrı bir rota yok (set, dersin flashcard görünümünde
              // açılır) — öneri dersin çalışma yüzeyine yönlendirir.
              onOpenCards={() => navigate(`/dersler/${oneriDersi.id}?view=flashcards`)}
              onOpenChapter={(chapterId) => navigate(`/dersler/${oneriDersi.id}/defter/${chapterId}`)}
            />
          ) : (
            <p className="text-sm text-stuhub-text-secondary">Henüz öneri üretecek bir ders yok.</p>
          )}
        </div>
        <div className="glass-panel feature-card">
          <div className="feature-card__top"><ChartLine size={20} aria-hidden="true" /><span>Haftalık Çalışma</span></div>
          {weeklyStudy ? (
            <div className="weekly-bars" aria-label="Haftalık çalışma grafiği">
              {weeklyStudy.days.map((entry) => {
                const date = new Date(`${entry.date}T12:00:00`)
                const day = date.toLocaleDateString('tr-TR', { weekday: 'short' }).replace('.', '')
                const max = Math.max(...weeklyStudy.days.map((item) => item.duration_sec), 1)
                const height = entry.duration_sec ? Math.max((entry.duration_sec / max) * 100, 8) : 0
                const isToday = entry.date === new Date().toISOString().slice(0, 10)
                const dakika = Math.round(entry.duration_sec / 60)
                return (
                  <div
                    key={entry.date}
                    role="img"
                    aria-label={`${day}: ${dakika} dk`}
                    className={`weekly-bar group relative ${isToday ? 'weekly-bar--today' : ''}`}
                  >
                    {/* Süre etiketi: native `title` (tarayıcı baloncuğu) yerine tasarım
                        token'larıyla cam baloncuk — TermTooltip deseniyle aynı
                        (radius-chip, glass-panel zemin/kenar, text-xs, mikro geçiş). */}
                    <span className="glass-panel pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 -translate-x-1/2 whitespace-nowrap rounded-chip px-2.5 py-1 text-xs font-medium text-stuhub-text opacity-0 transition-opacity duration-[var(--duration-micro)] group-hover:opacity-100">
                      {dakika} dk
                    </span>
                    <div className="weekly-bar__fill" style={{ height: `${height}%` }} />
                    <span>{day}</span>
                  </div>
                )
              })}
            </div>
          ) : weeklyHazir ? (
            <div className="empty-state min-h-[180px]"><ChartLine size={20} aria-hidden="true" /><p>Çalışma oturumların biriktikçe haftalık grafiğin burada görünecek.</p></div>
          ) : (
            /* Layout-shift: henüz veri yokken grafiğin gerçek kutusu (.weekly-bars:
               100px + 24px üst boşluk) iskelet çubuklarla rezerve edilir; veri
               gelince kart yüksekliği değişmez, alttaki paneller kaymaz. */
            <div className="weekly-bars" aria-busy="true">
              {Array.from({ length: 7 }, (_, index) => (
                <div key={`haftalik-iskelet-${index}`} className="weekly-bar">
                  <div className="weekly-bar__fill skeleton-block" style={{ height: '40%' }} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="home-grid">
        <Link to="/takvim" className="glass-panel glass-interactive feature-card"><div className="feature-card__top"><Calendar size={20} aria-hidden="true" /><span>Yaklaşan Takvim</span></div><p className="text-sm text-stuhub-text-secondary">Takvim görünümüne git.</p></Link>
        <Link to="/sinav-plani" className="glass-panel glass-interactive feature-card"><div className="feature-card__top"><Trophy size={20} aria-hidden="true" /><span>Sınav Planı</span></div><p className="text-sm text-stuhub-text-secondary">Ders bazındaki sınav planlarını incele.</p></Link>
      </div>

      <StreakRing />
    </section>
  )
}
