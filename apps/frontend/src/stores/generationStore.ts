import { create } from 'zustand'

import { streamFlashcardGeneration, type FlashcardSet } from '../api/flashcards'
import { streamNoteGeneration, type SavedNote } from '../api/notes'
import { streamOverallQuizGeneration, type OverallQuiz } from '../api/overall'
import { streamQuizGeneration, type Quiz } from '../api/quizzes'

export type GenerationKind = 'note' | 'quiz' | 'overall' | 'flashcards'

export interface GenerationJob {
  kind: GenerationKind
  targetId: number
  label: string
  percent: number
  message: string
  status: 'running' | 'done' | 'error'
  error: string | null
  liveContent: string
}

interface GenerationState {
  jobs: GenerationJob[]
  generateNote: (chapterId: number, chapterTitle: string) => Promise<SavedNote | null>
  generateQuiz: (chapterId: number, chapterTitle: string) => Promise<Quiz | null>
  generateOverallQuiz: (courseId: number, courseName: string) => Promise<OverallQuiz | null>
  generateFlashcards: (chapterId: number, chapterTitle: string) => Promise<FlashcardSet | null>
  clearJob: (kind: GenerationKind, targetId: number) => void
}

const DONE_JOB_TTL_MS = 8000

/** Üretimler sayfa değişse bile devam eder; ilerleme her sayfada görünür (madde 2). */
export const useGenerationStore = create<GenerationState>((set, get) => {
  const startJob = (kind: GenerationKind, targetId: number, label: string): GenerationJob | null => {
    if (get().jobs.some((j) => j.kind === kind && j.targetId === targetId && j.status === 'running')) {
      return null // aynı iş zaten sürüyor
    }
    const job: GenerationJob = {
      kind,
      targetId,
      label,
      percent: 0,
      message: 'Hazırlanıyor…',
      status: 'running',
      error: null,
      liveContent: '',
    }
    set((state) => ({ jobs: [job, ...state.jobs] }))
    return job
  }

  const update = (kind: GenerationKind, targetId: number, patch: Partial<GenerationJob>) => {
    set((state) => ({
      jobs: state.jobs.map((j) =>
        j.kind === kind && j.targetId === targetId ? { ...j, ...patch } : j,
      ),
    }))
  }

  const finishJob = (kind: GenerationKind, targetId: number, status: 'done' | 'error', error?: string) => {
    update(kind, targetId, { status, error: error ?? null, message: status === 'done' ? 'Tamamlandı.' : (error ?? 'Hata') })
    window.setTimeout(() => {
      set((state) => ({ jobs: state.jobs.filter((j) => !(j.kind === kind && j.targetId === targetId && (j.status === 'done' || j.status === 'error'))) }))
    }, DONE_JOB_TTL_MS)
  }

  return {
    jobs: [],

    generateNote: async (chapterId, chapterTitle) => {
      const job = startJob('note', chapterId, `Not: ${chapterTitle}`)
      if (!job) return null
      let result: SavedNote | null = null
      await streamNoteGeneration(chapterId, {
        onStatus: (percent, message) => update('note', chapterId, { percent, message }),
        onDelta: (text) => {
          const current = get().jobs.find((j) => j.kind === 'note' && j.targetId === chapterId)?.liveContent ?? ''
          update('note', chapterId, { liveContent: current + text })
        },
        onDone: (note) => {
          result = note
          update('note', chapterId, { percent: 100, message: 'Not hazır.' })
          finishJob('note', chapterId, 'done')
        },
        onError: (message) => finishJob('note', chapterId, 'error', message),
      })
      return result
    },

    generateQuiz: async (chapterId, chapterTitle) => {
      const job = startJob('quiz', chapterId, `Quiz: ${chapterTitle}`)
      if (!job) return null
      let result: Quiz | null = null
      await streamQuizGeneration(chapterId, {
        onStatus: (percent, message) => update('quiz', chapterId, { percent, message }),
        onDone: (quiz) => {
          result = quiz
          update('quiz', chapterId, { percent: 100, message: 'Quiz hazır.' })
          finishJob('quiz', chapterId, 'done')
        },
        onError: (message) => finishJob('quiz', chapterId, 'error', message),
      })
      return result
    },

    generateOverallQuiz: async (courseId, courseName) => {
      const job = startJob('overall', courseId, `Genel Quiz: ${courseName}`)
      if (!job) return null
      let result: OverallQuiz | null = null
      await streamOverallQuizGeneration(courseId, {
        onStatus: (percent, message) => update('overall', courseId, { percent, message }),
        onDone: (quiz) => {
          result = quiz
          update('overall', courseId, { percent: 100, message: 'Genel quiz hazır.' })
          finishJob('overall', courseId, 'done')
        },
        onError: (message) => finishJob('overall', courseId, 'error', message),
      })
      return result
    },

    generateFlashcards: async (chapterId, chapterTitle) => {
      const job = startJob('flashcards', chapterId, `Kartlar: ${chapterTitle}`)
      if (!job) return null
      let result: FlashcardSet | null = null
      await streamFlashcardGeneration(chapterId, {
        onStatus: (percent, message) => update('flashcards', chapterId, { percent, message }),
        onDone: (set) => {
          result = set
          update('flashcards', chapterId, { percent: 100, message: 'Kartlar hazır.' })
          finishJob('flashcards', chapterId, 'done')
        },
        onError: (message) => finishJob('flashcards', chapterId, 'error', message),
      })
      return result
    },

    clearJob: (kind, targetId) => {
      set((state) => ({ jobs: state.jobs.filter((j) => !(j.kind === kind && j.targetId === targetId)) }))
    },
  }
})
