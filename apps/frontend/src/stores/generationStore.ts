import { create } from 'zustand'

import { streamFlashcardGeneration, type FlashcardSet } from '../api/flashcards'
import { streamNoteGeneration, type SavedNote } from '../api/notes'
import { streamOverallQuizGeneration, type OverallQuiz } from '../api/overall'
import { alertDialog } from './alertStore'

export type GenerationKind = 'note' | 'overall' | 'flashcards'

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
  generateOverallQuiz: (courseId: number, courseName: string) => Promise<OverallQuiz | null>
  generateFlashcards: (chapterId: number, chapterTitle: string) => Promise<FlashcardSet | null>
  clearJob: (kind: GenerationKind, targetId: number) => void
}

const DONE_JOB_TTL_MS = 8000

// Her üretim, dakikalarca açık kalan bir SSE bağlantısı tutar. Tarayıcı HTTP/1.1'de
// origin başına 6 bağlantıya izin verir; sınırsız eşzamanlı üretim bu bütçeyi bitirip
// sayfanın DİĞER tüm isteklerini (veri yüklemesi, yoklamalar) süresiz kuyruğa sokuyordu
// — arayüz "Yükleniyor…"da donuyor, yalnızca yenileme kurtarıyordu (2026-09-08).
// ponytail: sabit 2 slot; sunucu HTTP/2'ye geçerse bu kapı tamamen kaldırılabilir.
const MAX_CONCURRENT_STREAMS = 2

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

  let activeStreams = 0
  const waiting: (() => void)[] = []

  /** Akışı boş bir bağlantı slotu açılana kadar bekletir. */
  const withStreamSlot = async <T,>(
    kind: GenerationKind,
    targetId: number,
    run: () => Promise<T>,
  ): Promise<T> => {
    if (activeStreams >= MAX_CONCURRENT_STREAMS) {
      update(kind, targetId, { message: 'Sırada bekliyor…' })
      await new Promise<void>((resolve) => waiting.push(resolve))
    }
    activeStreams += 1
    try {
      return await run()
    } finally {
      activeStreams -= 1
      waiting.shift()?.()
    }
  }

  const finishJob = (kind: GenerationKind, targetId: number, status: 'done' | 'error', error?: string) => {
    update(kind, targetId, { status, error: error ?? null, message: status === 'done' ? 'Tamamlandı.' : (error ?? 'Hata') })
    if (status === 'error' && error) {
      // Küçük panel satırı gözden kaçabilir — ön koşul hataları ("önce not oluştur" gibi)
      // özellikle net görülmeli, o yüzden ayrıca tema uyumlu bir bilgi diyaloğu da gösterilir.
      void alertDialog(error)
    }
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
      await withStreamSlot('note', chapterId, () => streamNoteGeneration(chapterId, {
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
      }))
      return result
    },

    generateOverallQuiz: async (courseId, courseName) => {
      const job = startJob('overall', courseId, `Genel Quiz: ${courseName}`)
      if (!job) return null
      let result: OverallQuiz | null = null
      await withStreamSlot('overall', courseId, () => streamOverallQuizGeneration(courseId, {
        onStatus: (percent, message) => update('overall', courseId, { percent, message }),
        onDone: (quiz) => {
          result = quiz
          update('overall', courseId, { percent: 100, message: 'Genel quiz hazır.' })
          finishJob('overall', courseId, 'done')
        },
        onError: (message) => finishJob('overall', courseId, 'error', message),
      }))
      return result
    },

    generateFlashcards: async (chapterId, chapterTitle) => {
      const job = startJob('flashcards', chapterId, `Kartlar: ${chapterTitle}`)
      if (!job) return null
      let result: FlashcardSet | null = null
      await withStreamSlot('flashcards', chapterId, () => streamFlashcardGeneration(chapterId, {
        onStatus: (percent, message) => update('flashcards', chapterId, { percent, message }),
        onDone: (set) => {
          result = set
          update('flashcards', chapterId, { percent: 100, message: 'Kartlar hazır.' })
          finishJob('flashcards', chapterId, 'done')
        },
        onError: (message) => finishJob('flashcards', chapterId, 'error', message),
      }))
      return result
    },

    clearJob: (kind, targetId) => {
      set((state) => ({ jobs: state.jobs.filter((j) => !(j.kind === kind && j.targetId === targetId)) }))
    },
  }
})
