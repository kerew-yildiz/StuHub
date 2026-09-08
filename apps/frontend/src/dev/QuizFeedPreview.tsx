import { QuizFeed } from '../components/QuizFeed'

/** Tamamen mock'lanmış global `fetch` — gerçek backend/oturum gerektirmez.
 * Gerçekçi ağ gecikmesi (200-400ms) simüle eder ki glitch gerçek koşullarda
 * göründüğü gibi görünsün. */
function installMockFetch() {
  let nextId = 1
  const makeBatch = (count: number) => ({
    items: Array.from({ length: count }, () => {
      const id = nextId++
      return {
        feed_id: id,
        question: `Soru ${id}: Bu bir test sorusudur, cevap seçeneklerinden birini seç.`,
        options: ['Seçenek A', 'Seçenek B', 'Seçenek C', 'Seçenek D'],
        topic: 'Test Konusu',
        chapter_id: 1,
        difficulty: 'medium',
      }
    }),
    pool_ready: 25,
    generating: false,
  })

  const originalFetch = window.fetch.bind(window)
  window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const delay = 200 + Math.random() * 200
    await new Promise((resolve) => setTimeout(resolve, delay))

    if (url.includes('/api/courses/') && url.includes('/feed?')) {
      const limitMatch = url.match(/limit=(\d+)/)
      const limit = limitMatch ? Number(limitMatch[1]) : 5
      return new Response(JSON.stringify(makeBatch(limit)), { status: 200 })
    }
    if (url.includes('/feed/') && url.includes('/answer')) {
      return new Response(
        JSON.stringify({
          correct: true,
          correct_index: 0,
          explanation: 'Test açıklaması.',
          citations: null,
          note_id: null,
          chapter_id: 1,
        }),
        { status: 200 },
      )
    }
    if (url.includes('/feed/skip')) {
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    }
    return originalFetch(input, init)
  }) as typeof fetch
}

installMockFetch()

export default function QuizFeedPreview() {
  return (
    <div style={{ padding: 24, background: '#1c1c1e', minHeight: '100vh' }}>
      <QuizFeed courseId={999} />
    </div>
  )
}
