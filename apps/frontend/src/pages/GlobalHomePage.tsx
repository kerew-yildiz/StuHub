import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { coursesApi, type Course } from '../api/courses'
import { termsApi, type Term } from '../api/terms'
import { NextActionCard } from '../components/NextActionCard'
import { getWeeklyStudy, type WeeklyStudy } from '../api/streaks'
import { StreakRing } from '../components/StreakRing'
import { ArrowRight, BookOpen, Calendar, ChartLine, Crosshair, Trophy } from 'lucide-react'

export function GlobalHomePage() {
  const [terms, setTerms] = useState<Term[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [weeklyStudy, setWeeklyStudy] = useState<WeeklyStudy | null>(null)

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      termsApi.list().then(async (items) => {
        if (cancelled) return
        setTerms(items)
        const entries = await Promise.all(items.map(async (term) => await coursesApi.listByTerm(term.id).catch(() => [])))
        if (!cancelled) setCourses(entries.flat())
      }),
      getWeeklyStudy().then((data) => { if (!cancelled) setWeeklyStudy(data) }).catch(() => undefined),
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
          {courses[0] ? <NextActionCard courseId={courses[0].id} /> : <p className="text-sm text-stuhub-text-secondary">Henüz öneri üretecek bir ders yok.</p>}
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
                return <div key={entry.date} className={`weekly-bar ${isToday ? 'weekly-bar--today' : ''}`}><div className="weekly-bar__fill" style={{ height: `${height}%` }} title={`${Math.round(entry.duration_sec / 60)} dk`} /><span>{day}</span></div>
              })}
            </div>
          ) : (
            <div className="empty-state min-h-[180px]"><ChartLine size={20} aria-hidden="true" /><p>Çalışma oturumların biriktikçe haftalık grafiğin burada görünecek.</p></div>
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
