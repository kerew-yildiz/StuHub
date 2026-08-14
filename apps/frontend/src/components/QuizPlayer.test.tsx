import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Quiz } from '../api/quizzes'
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
})
