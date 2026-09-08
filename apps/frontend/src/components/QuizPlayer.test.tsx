import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { submitAttempt, type AttemptOutcome, type Quiz } from '../api/quizzes'
import { QuizPlayer } from './QuizPlayer'

afterEach(() => cleanup())

vi.mock('../api/quizzes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/quizzes')>()
  return {
    ...actual,
    listAttempts: vi.fn(async () => []),
    removeAttempt: vi.fn(async () => {}),
    removeQuiz: vi.fn(async () => {}),
    submitAttempt: vi.fn(async () => ({
      attempt_id: 1,
      score: 100,
      total: 2,
      correct_count: 2,
      results: [
        {
          qid: '0-0',
          question: 'S1?',
          selected_index: 0,
          correct_index: 0,
          correct: true,
          feedback: 'Doğru! Pekiştirme.',
          explanation: 'x',
          citations: [],
          options: ['A', 'B', 'C', 'D'],
        },
        {
          qid: '0-1',
          question: 'S2?',
          selected_index: 2,
          correct_index: 2,
          correct: true,
          feedback: 'Doğru!',
          explanation: 'x',
          citations: [],
          options: ['A', 'B', 'C', 'D'],
        },
      ],
    })),
  }
})

// Derin bağlantı: "Notta gör" notu chapter üzerinden okur
vi.mock('../api/notes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/notes')>()
  return {
    ...actual,
    getNote: vi.fn(async () => ({
      id: 5,
      chapter_id: 1,
      content_md: '## Konu A\n\nKonu A notunun gövdesi.\n\n## Konu B\n\nBaşka bölüm.',
      citations_json: { topics: [] },
      topics_json: [],
      generated_at: '2026-01-01T00:00:00Z',
      model_used: null,
    })),
  }
})

// PDF önizlemesi gerçek dosya indirmesin — blob URL'i sabitlenir
vi.mock('../lib/useAuthedFileUrl', () => ({
  useAuthedFileUrl: () => ({ blobUrl: 'blob:mock-pdf', loading: false, error: false }),
}))

const quiz: Quiz = {
  id: 1,
  chapter_id: 1,
  questions_json: {
    topics: [
      {
        topic: 'Konu A',
        questions: [
          {
            topic: 'Konu A',
            question: 'S1?',
            options: ['A', 'B', 'C', 'D'],
            correct_index: 0,
            explanation: 'Açıklama',
            feedback_correct: 'Doğru! Pekiştirme.',
            feedback_wrong: 'Yanlış.',
            citations: [],
          },
          {
            topic: 'Konu A',
            question: 'S2?',
            options: ['A', 'B', 'C', 'D'],
            correct_index: 2,
            explanation: 'Açıklama',
            feedback_correct: 'Doğru!',
            feedback_wrong: 'Yanlış.',
            citations: [],
          },
        ],
      },
    ],
  },
}

/** İki soru da yanlış: ilki atıflı (bağlantı almalı), ikincisi atıfsız (bağlantı almamalı). */
const wrongOutcome: AttemptOutcome = {
  attempt_id: 2,
  score: 0,
  total: 2,
  correct_count: 0,
  results: [
    {
      qid: '0-0',
      question: 'S1?',
      selected_index: 1,
      correct_index: 0,
      correct: false,
      feedback: 'Yanlış.',
      explanation: 'x',
      citations: [
        {
          id: 1,
          source_type: 'textbook',
          source_id: 9,
          page: 41,
          slide: null,
          chunk_id: 'chk_1_9_3',
          quote: 'kaynak alıntısı',
        },
      ],
      options: ['A', 'B', 'C', 'D'],
    },
    {
      qid: '0-1',
      question: 'S2?',
      selected_index: 0,
      correct_index: 2,
      correct: false,
      feedback: 'Yanlış.',
      explanation: 'x',
      citations: [],
      options: ['A', 'B', 'C', 'D'],
    },
  ],
}

/** Her iki soruyu yanlış cevaplayıp özet ekranına geçer. */
async function finishAllWrong() {
  vi.mocked(submitAttempt).mockResolvedValueOnce(wrongOutcome)
  render(<QuizPlayer quiz={quiz} />)
  await screen.findByText('S1?')

  fireEvent.click(screen.getByRole('button', { name: 'B' }))
  fireEvent.click(screen.getByRole('button', { name: 'Sonraki soru' }))
  fireEvent.click(screen.getByRole('button', { name: 'A' }))
  fireEvent.click(screen.getByRole('button', { name: 'Bitir' }))

  await screen.findByText('Quiz tamamlandı')
}

describe('QuizPlayer', () => {
  it('tek soru gösterir ve anında feedback verir', async () => {
    render(<QuizPlayer quiz={quiz} />)
    await screen.findByText('S1?')

    // doğru şıkkı seç
    fireEvent.click(screen.getByRole('button', { name: 'A' }))
    expect(screen.getByRole('status')).toHaveTextContent('Doğru! Pekiştirme.')
  })

  it('tamamlanınca özet gösterir', async () => {
    render(<QuizPlayer quiz={quiz} />)
    await screen.findByText('S1?')

    fireEvent.click(screen.getByRole('button', { name: 'A' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sonraki soru' }))
    expect(screen.getByText('S2?')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'C' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bitir' }))

    expect(await screen.findByText('Quiz tamamlandı')).toBeInTheDocument()
    expect(screen.getByText('100 / 100')).toBeInTheDocument()
    expect(screen.getByText('2 / 2 doğru')).toBeInTheDocument()
  })

  it('doğru cevapta derin bağlantı çıkmaz', async () => {
    render(<QuizPlayer quiz={quiz} />)
    await screen.findByText('S1?')

    fireEvent.click(screen.getByRole('button', { name: 'A' }))
    fireEvent.click(screen.getByRole('button', { name: 'Sonraki soru' }))
    fireEvent.click(screen.getByRole('button', { name: 'C' }))
    fireEvent.click(screen.getByRole('button', { name: 'Bitir' }))
    await screen.findByText('Quiz tamamlandı')

    expect(screen.queryByRole('button', { name: /Notta gör/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Kaynak sayfa/ })).not.toBeInTheDocument()
  })

  it('yalnızca atıflı yanlış soruya not ve kaynak bağlantısı ekler', async () => {
    await finishAllWrong()

    // iki soru da yanlış ama yalnızca atıflı olanda bağlantı var (kırık link üretilmez)
    expect(screen.getAllByRole('button', { name: /Notta gör/ })).toHaveLength(1)
    const sourceLinks = screen.getAllByRole('button', { name: /Kaynak sayfa/ })
    expect(sourceLinks).toHaveLength(1)
    expect(sourceLinks[0]).toHaveTextContent('sayfa 41')
  })

  it('"Notta gör" konuya karşılık gelen not bölümünü açar', async () => {
    await finishAllWrong()

    fireEvent.click(screen.getByRole('button', { name: /Notta gör/ }))

    expect(await screen.findByText('Notta: Konu A')).toBeInTheDocument()
    expect(screen.getByText('Konu A notunun gövdesi.')).toBeInTheDocument()
    // eşleşmeyen bölüm taşınmaz
    expect(screen.queryByText('Başka bölüm.')).not.toBeInTheDocument()
  })

  it('"Kaynak sayfa" PDF önizlemesini atıf sayfasında açar', async () => {
    await finishAllWrong()

    fireEvent.click(screen.getByRole('button', { name: /Kaynak sayfa/ }))

    expect(await screen.findByText('Kaynak · sayfa 41')).toBeInTheDocument()
    const frame = document.querySelector('iframe')
    expect(frame?.getAttribute('src')).toBe('blob:mock-pdf#page=41')
  })
})
