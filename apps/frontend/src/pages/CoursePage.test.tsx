import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CoursePage } from './CoursePage'

// Sayfa + gorunum bilesenleri tum istekleri `api/client` uzerinden yapar; burada bos
// govdelerle karsilanir (ag trafigi yok). Alan adi bazli birkac sekil, bilesenlerin
// bekledigi alanlari (orn. `chapters`) bos dizi olarak dondurur.
vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {},
  BASE_URL: '/api',
  setAccessToken: vi.fn(),
  authFetch: vi.fn(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })),
  apiFetch: vi.fn(async (yol: string) => {
    if (/^\/courses\/\d+$/.test(yol)) return { id: 1, name: 'Psikoloji', term_id: 1, instructor: null }
    if (yol.endsWith('/card-summary')) return { course_id: 1, chapters: [] }
    if (yol.endsWith('/heatmap')) return { course_id: 1, weights: {}, topics: [] }
    if (yol.endsWith('/abandoned')) return { topics: [] }
    if (yol.endsWith('/next-action')) return { action: 'none', reason: 'Test', title: 'Test' }
    if (yol.endsWith('/retention-progress')) return { points: [], mastered: 0, total: 0 }
    if (yol.endsWith('/topic-progress')) return { total_topics: 0, completed_topics: 0, topics: [] }
    return []
  }),
}))

afterEach(() => {
  cleanup()
})

/** Gercek uygulamadaki sidebar/dashboard gezinmesini taklit eden route kabi: gorunum
 * degisimi URL (`view`) uzerinden yapilir — tiklama disinda bir yol yoktur. */
function DersRota() {
  return (
    <>
      <nav aria-label="test-gorunumler">
        <Link to="/dersler/1">genel</Link>
        {[
          'notes',
          'saved',
          'flashcards',
          'material-ask',
          'errors',
          'heatmap',
          'assignment-evaluation',
          'swipe-quiz',
          'assignment-draft-coach',
          'bilinmeyen-view',
        ].map((view) => (
          <Link key={view} to={`/dersler/1?view=${view}`}>
            {view}
          </Link>
        ))}
      </nav>
      <CoursePage />
    </>
  )
}

const ciz = (rota = '/dersler/1') =>
  render(
    <MemoryRouter initialEntries={[rota]}>
      <Routes>
        <Route path="/dersler/:courseId" element={<DersRota />} />
      </Routes>
    </MemoryRouter>,
  )

const bekleTekKok = async (beklenen: string) => {
  const kokler = () => Array.from(document.querySelectorAll('[data-view-root]'))
  await waitFor(() => expect(kokler()).toHaveLength(1))
  expect(kokler()[0].getAttribute('data-view-root')).toBe(beklenen)
}

/** URL -> (beklenen gorunum koku, o gorunume ait ekranda gorunen imza metni). */
const GORUNUMLER: ReadonlyArray<readonly [string, string, string]> = [
  ['flashcards', 'cards', 'Bugünün Kartları'],
  ['material-ask', 'ask', 'Materyale Sor'],
  ['notes', 'notes', 'Notlar'],
  ['saved', 'saved', 'Kaydedilenler'],
  ['assignment-evaluation', 'essay', 'Ödev Değerlendir'],
  ['errors', 'errors', 'Hatalarım'],
  ['heatmap', 'heatmap', 'Zayıf Konu Isı Haritası'],
]

describe('CoursePage sekme izolasyonu', () => {
  it('her gecisten sonra DOM icinde YALNIZ o gorunum koku kalir', async () => {
    ciz()

    for (const [view, kok, imza] of GORUNUMLER) {
      fireEvent.click(screen.getByRole('link', { name: view }))

      await bekleTekKok(kok)
      expect(await screen.findByText(imza)).toBeInTheDocument()

      // Onceki gorunumun icerigi gercekten unmount oldu mu? (kullanicinin gordugu sizinti)
      for (const [digerView, , digerImza] of GORUNUMLER) {
        if (digerView === view) continue
        expect(screen.queryByText(digerImza)).toBeNull()
      }
      expect(screen.queryByText("Chapter'lar")).toBeNull()
    }
  })

  it('hizli ard arda gecis sonrasi tek gorunum kalir (Notlar + Materyale Sor merge olmaz)', async () => {
    ciz()

    // Kullanici akisi: Materyale Sor -> Notlar -> Aninda Kaydedilenler (beklemeden)
    fireEvent.click(screen.getByRole('link', { name: 'material-ask' }))
    fireEvent.click(screen.getByRole('link', { name: 'notes' }))
    fireEvent.click(screen.getByRole('link', { name: 'saved' }))
    fireEvent.click(screen.getByRole('link', { name: 'flashcards' }))

    await bekleTekKok('cards')
    expect(screen.queryByText('Materyale Sor')).toBeNull()
    expect(screen.queryByText('Kaydedilenler')).toBeNull()
  })

  it('klavye kisayolu icerigi URL ile ayni tutar (eski sekme icerigi ekranda kalmaz)', async () => {
    ciz()

    // 2 -> "Pratik Yap" grubunun ilk sekmesi: Kartlar
    fireEvent.keyDown(window, { key: '2' })
    await bekleTekKok('cards')

    fireEvent.click(screen.getByRole('link', { name: 'notes' }))
    await bekleTekKok('notes')
    expect(screen.queryByText('Bugünün Kartları')).toBeNull()
    expect(await screen.findByText('Notlar')).toBeInTheDocument()
  })

  it('taninmayan view degeri guvenli varsayilana (overview) duser', async () => {
    ciz('/dersler/1?view=bilinmeyen-view')

    await bekleTekKok('overview')
    expect(screen.getByText("Chapter'lar")).toBeInTheDocument()
  })
})
