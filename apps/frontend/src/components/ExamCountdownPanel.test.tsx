import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ExamCountdownPanel } from './ExamCountdownPanel'
import { RetentionCurve } from './RetentionCurve'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** URL kalıbına göre yanıt veren tek `fetch` sahtesi; çağrıları da kaydeder. */
function stubRoutes(routes: Array<[RegExp, (init?: RequestInit) => Response]>) {
  const calls: Array<{ url: string; method: string }> = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      calls.push({ url, method: init?.method ?? 'GET' })
      for (const [pattern, handler] of routes) {
        if (pattern.test(`${init?.method ?? 'GET'} ${url}`)) return handler(init)
      }
      throw new Error(`Beklenmeyen istek: ${init?.method ?? 'GET'} ${url}`)
    }),
  )
  return calls
}

function exam(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    course_id: 1,
    title: 'Vize',
    exam_date: '2026-06-10',
    chapter_ids: [],
    days_left: 3,
    created_at: '2026-06-01 09:00:00',
    ...overrides,
  }
}

describe('ExamCountdownPanel', () => {
  it('sınavları geri sayımla listeler ve plan uçtan yüklenir', async () => {
    stubRoutes([
      [/GET .*\/api\/courses\/1\/exams$/, () => json([exam()])],
      [
        /GET .*\/api\/exams\/7\/plan$/,
        () =>
          json({
            exam: exam(),
            total_cards: 3,
            days: [
              {
                date: '2026-06-08',
                card_count: 2,
                cards: [
                  { set_id: 1, card_index: 0, topic: 'Ağaçlar', front: 'AVL nedir?' },
                  { set_id: 1, card_index: 1, topic: 'Ağaçlar', front: 'Rotasyon nedir?' },
                ],
              },
              {
                date: '2026-06-09',
                card_count: 1,
                cards: [{ set_id: 1, card_index: 2, topic: 'Yığınlar', front: 'Heap nedir?' }],
              },
            ],
          }),
      ],
    ])

    render(<ExamCountdownPanel courseId={1} />)

    expect(await screen.findByText('3 gün kaldı')).toBeInTheDocument()
    expect(screen.getByText('Vize')).toBeInTheDocument()
    expect(screen.getByText('Tüm ders')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Çalışma planı/ }))

    expect(await screen.findByText('AVL nedir?')).toBeInTheDocument()
    expect(screen.getByText('Heap nedir?')).toBeInTheDocument()
    expect(screen.getByText('3 kart, 2 güne bölündü.')).toBeInTheDocument()
  })

  it('form gönderimi sınavı POST eder ve listeye ekler', async () => {
    const calls = stubRoutes([
      [/GET .*\/api\/courses\/1\/exams$/, () => json([])],
      [
        /POST .*\/api\/courses\/1\/exams$/,
        () => json(exam({ id: 9, title: 'Final', exam_date: '2030-07-01', days_left: 24 }), 201),
      ],
    ])

    render(<ExamCountdownPanel courseId={1} />)
    expect(await screen.findByText(/Henüz sınav eklemedin/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Sınav adı'), { target: { value: 'Final' } })
    // `min` bugüne eşit — geçmiş tarih tarayıcı doğrulamasına takılır, ileri tarih seçilir.
    fireEvent.change(screen.getByLabelText('Sınav tarihi'), { target: { value: '2030-07-01' } })
    fireEvent.click(screen.getByRole('button', { name: /Sınav ekle/ }))

    expect(await screen.findByText('Final')).toBeInTheDocument()
    expect(screen.getByText('24 gün kaldı')).toBeInTheDocument()

    const posted = calls.find((call) => call.method === 'POST')
    expect(posted?.url).toBe('/api/courses/1/exams')
  })

  it('silme düğmesi DELETE atar ve kaydı listeden düşürür', async () => {
    const calls = stubRoutes([
      [/GET .*\/api\/courses\/1\/exams$/, () => json([exam()])],
      [/DELETE .*\/api\/exams\/7$/, () => json(null, 204)],
    ])

    render(<ExamCountdownPanel courseId={1} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Vize sınavını sil' }))

    await waitFor(() => expect(screen.queryByText('Vize')).not.toBeInTheDocument())
    expect(calls.some((call) => call.method === 'DELETE' && call.url === '/api/exams/7')).toBe(true)
  })
})

describe('RetentionCurve', () => {
  it('konu eğrilerini SVG olarak çizer ve bugünkü oranı gösterir', async () => {
    stubRoutes([
      [
        /GET .*\/api\/courses\/1\/retention/,
        () =>
          json({
            course_id: 1,
            horizon_days: 12,
            generated_at: '2026-06-01T09:00:00+00:00',
            topics: [
              {
                topic: 'Soğuk Konu',
                card_count: 3,
                reviewed_count: 0,
                current: 0,
                points: [
                  { day: 0, retention: 0 },
                  { day: 6, retention: 0 },
                  { day: 12, retention: 0 },
                ],
              },
              {
                topic: 'Taze Konu',
                card_count: 2,
                reviewed_count: 2,
                current: 1,
                points: [
                  { day: 0, retention: 1 },
                  { day: 6, retention: 0.9 },
                  { day: 12, retention: 0.81 },
                ],
              },
            ],
          }),
      ],
    ])

    const { container } = render(<RetentionCurve courseId={1} days={12} />)

    expect(
      await screen.findByRole('img', { name: 'Konu bazlı unutma eğrisi, 12 günlük tahmin' }),
    ).toBeInTheDocument()
    expect(container.querySelectorAll('polyline')).toHaveLength(2)
    expect(screen.getByText('Soğuk Konu')).toBeInTheDocument()
    expect(screen.getByText('bugün %0')).toBeInTheDocument()
    expect(screen.getByText('bugün %100')).toBeInTheDocument()
    expect(screen.getByText('2/2 kart çalışıldı')).toBeInTheDocument()
  })

  it('konu yoksa yönlendirici boş durum gösterir', async () => {
    stubRoutes([
      [
        /GET .*\/api\/courses\/1\/retention/,
        () =>
          json({
            course_id: 1,
            horizon_days: 30,
            generated_at: '2026-06-01T09:00:00+00:00',
            topics: [],
          }),
      ],
    ])

    render(<RetentionCurve courseId={1} />)

    expect(await screen.findByText(/önce bu derste flashcard oluştur/)).toBeInTheDocument()
  })
})
