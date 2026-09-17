import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { chaptersApi, type Chapter } from '../api/chapters'
import { listChapterNotes, type SavedNote } from '../api/notes'
import { formatDateShort } from '../lib/format'
import { LoaderCircle, FileText } from 'lucide-react'

interface CourseNotesPanelProps {
  courseId: number
}

export function CourseNotesPanel({ courseId }: CourseNotesPanelProps) {
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [notes, setNotes] = useState<Record<number, SavedNote[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void chaptersApi.listByCourse(courseId).then(async (items) => {
      if (cancelled) return
      setChapters(items)
      const entries = await Promise.all(items.map(async (chapter) => {
        // Arşiv ucu yeniden eskiye (id DESC) döner; frontend de sırayı garantiler.
        const archive = await listChapterNotes(chapter.id)
        return [chapter.id, archive.sort((a, b) => b.id - a.id)] as const
      }))
      if (!cancelled) setNotes(Object.fromEntries(entries))
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [courseId])

  if (loading) {
    return <div className="glass-panel-subtle flex items-center gap-2 p-4 text-sm text-stuhub-text-secondary"><LoaderCircle className="animate-spin" size={16} /> Notlar yükleniyor…</div>
  }

  return (
    <section className="page-shell">
      <header className="page-header">
        <div>
          <h2 className="page-title">Notlar</h2>
          <p className="page-subtitle">Chapter'lara göre üretilen tüm notlarını burada gör.</p>
        </div>
      </header>
      <div className="list-stack">
        {chapters.map((chapter) => {
          const chapterNotes = notes[chapter.id] ?? []
          return (
            <section key={chapter.id}>
              <h3 className="section-title mb-2">{chapter.title}</h3>
              {chapterNotes.length > 0 ? (
                <div className="list-stack">
                  {chapterNotes.map((note) => (
                    <Link key={note.id} to={`/dersler/${courseId}/defter/${chapter.id}?view=notes`} className="glass-panel glass-interactive list-card">
                      <div className="flex min-w-0 items-center gap-3">
                        <FileText size={17} className="shrink-0 text-stuhub-text-secondary" aria-hidden="true" />
                        <span className="truncate text-sm">Not</span>
                        <span className="text-xs text-stuhub-text-muted">{formatDateShort(note.generated_at)}</span>
                      </div>
                      <span className="text-xs text-stuhub-text-muted">Aç</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="glass-panel-subtle flex items-center gap-3 px-4 py-3 text-sm text-stuhub-text-secondary">
                  <FileText size={16} aria-hidden="true" />
                  <span>Bu chapter için henüz not üretmedin.</span>
                </div>
              )}
            </section>
          )
        })}
        {chapters.length === 0 && <div className="glass-panel-subtle p-5 text-sm text-stuhub-text-secondary">Henüz chapter bulunmuyor.</div>}
      </div>
    </section>
  )
}
