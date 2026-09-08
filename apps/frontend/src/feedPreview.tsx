import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { QuizFeed } from './components/QuizFeed'
import './styles/theme.css'

/* GEÇİCİ görsel doğrulama girişi — backend feed ucu hazır olmadan QuizFeed'i
 * sahte veriyle tarayıcıda görmek için. Doğrulamadan sonra silinir. */

const items = Array.from({ length: 10 }, (_, i) => ({
  feed_id: i + 1,
  question: `Hücre zarının seçici geçirgenliği hangi mekanizmayla açıklanır? (${i + 1})`,
  options: [
    'Basit difüzyon yalnızca büyük moleküller için çalışır',
    'Fosfolipit çift tabaka ve taşıyıcı proteinler birlikte',
    'Sadece aktif taşıma ile',
    'Zar geçirgen değildir',
  ],
  topic: 'Hücre zarı',
  chapter_id: 1,
  difficulty: (['easy', 'medium', 'hard'] as const)[i % 3],
}))

window.fetch = (async (input: RequestInfo | URL) => {
  const url = String(input)
  const body = url.includes('/feed?')
    ? { items, pool_ready: 42, generating: false }
    : url.includes('/answer')
      ? {
          correct: false,
          correct_index: 1,
          explanation:
            'Fosfolipit çift tabaka apolar molekülleri geçirir; polar/iyonik maddeler taşıyıcı proteinlere ihtiyaç duyar.',
          citations: [
            { id: 1, source_type: 'textbook', source_id: 9, page: 41, slide: null, chunk_id: 'c', quote: 'q' },
          ],
          note_id: 5,
          chapter_id: 1,
        }
      : { ok: true }
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}) as typeof window.fetch

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div className="min-h-dvh bg-stuhub-bg p-8 text-stuhub-text">
      <h1 className="mb-4 text-2xl font-semibold">Soru Akışı</h1>
      <QuizFeed courseId={1} />
    </div>
  </StrictMode>,
)
