import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { OverallQuiz } from '../api/overall'
import { OverallQuizPlayer } from './OverallQuizPlayer'

afterEach(() => cleanup())

vi.mock('../api/overall', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/overall')>()
  return {
    ...actual,
    listOverallAttempts: vi.fn(async () => []),
    removeOverallAttempt: vi.fn(async () => {}),
    removeOverallQuiz: vi.fn(async () => {}),
    submitOverallAttempt: vi.fn(async () => ({
      attempt_id: 1,
      score: 80,
      closed_correct: 2,
      closed_total: 2,
      open_total: 0,
      results: [
        {
          qid: 0,
          type: 'mcq',
          question: 'MCQ sorusu?',
          correct: true,
          feedback: 'Doğru!',
          explanation: 'e',
          citations: [],
        },
        {
          qid: 1,
          type: 'fib',
          question: 'Bağlı liste ____ yapıdır.',
          correct: true,
          feedback: 'Doğru!',
          explanation: 'e',
          citations: [],
        },
      ],
    })),
  }
})

const quiz: OverallQuiz = {
  id: 1,
  course_id: 1,
  questions_json: {
    seed: 42,
    questions: [
      {
        type: 'mcq',
        topic: 'Konu A',
        question: 'MCQ sorusu?',
        options: ['A', 'B', 'C', 'D'],
        correct_index: 0,
        explanation: 'Açıklama',
        feedback_correct: 'Doğru! Pekiştirme.',
        feedback_wrong: 'Yanlış.',
        citations: [],
      },
      {
        type: 'fib',
        topic: 'Konu A',
        text: 'Bağlı liste ____ yapıdır.',
        accepted_answers: ['doğrusal'],
        explanation: 'Açıklama',
        feedback_correct: 'Doğru!',
        feedback_wrong: 'Yanlış.',
        citations: [],
      },
    ],
  },
}

describe('OverallQuizPlayer', () => {
  it('mcq anında feedback verir, fib cevap ister ve özet gösterir', async () => {
    render(<OverallQuizPlayer quiz={quiz} />)
    await screen.findByText('MCQ sorusu?')

    fireEvent.click(screen.getByRole('button', { name: 'A' }))
    expect(screen.getByRole('status')).toHaveTextContent('Doğru! Pekiştirme.')

    fireEvent.click(screen.getByRole('button', { name: 'Sonraki soru' }))
    expect(screen.getByText('Bağlı liste ____ yapıdır.')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Cevabını yaz…'), {
      target: { value: 'doğrusal' },
    })
    fireEvent.click(screen.getByRole('button', { name: "Quiz'i Bitir" }))

    expect(await screen.findByText('Genel quiz tamamlandı')).toBeInTheDocument()
    expect(screen.getByText('80 / 100')).toBeInTheDocument()
  })

  it('0 soruluk quizde çökmez, boş durum ve silme seçeneği gösterir', async () => {
    // Prod'da üretimi tamamen başarısız olmuş 1 kayıt vardı (questions: []); oynatıcı
    // `questions[0].type` okuyup "Cannot read properties of undefined (reading 'type')"
    // ile tüm CoursePage'i düşürüyordu.
    const onDelete = vi.fn()
    const empty: OverallQuiz = { ...quiz, questions_json: { seed: 1, questions: [] } }

    render(<OverallQuizPlayer quiz={empty} onDelete={onDelete} />)

    expect(await screen.findByText('Bu genel quizde hiç soru yok')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Quizi sil' }))
    expect(onDelete).toHaveBeenCalledWith(empty.id)
  })
})
