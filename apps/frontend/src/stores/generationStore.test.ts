import { describe, expect, it, vi } from 'vitest'

import { useGenerationStore } from './generationStore'

const stream = vi.hoisted(() => ({ started: [] as number[], release: [] as (() => void)[] }))

vi.mock('../api/flashcards', () => ({
  streamFlashcardGeneration: (chapterId: number) => {
    stream.started.push(chapterId)
    return new Promise<void>((resolve) => stream.release.push(resolve))
  },
}))
vi.mock('../api/notes', () => ({ streamNoteGeneration: vi.fn() }))
vi.mock('../api/overall', () => ({ streamOverallQuizGeneration: vi.fn() }))

describe('generationStore akış slotu', () => {
  it('aynı anda en fazla 2 akış açar, fazlasını kuyrukta bekletir', async () => {
    const store = useGenerationStore.getState()
    void store.generateFlashcards(1, 'A')
    void store.generateFlashcards(2, 'B')
    void store.generateFlashcards(3, 'C')
    await Promise.resolve()

    // Tarayıcı origin başına 6 bağlantı verir; 3. akış slot boşalana kadar başlamamalı.
    expect(stream.started).toEqual([1, 2])
    expect(
      useGenerationStore.getState().jobs.find((j) => j.targetId === 3)?.message,
    ).toBe('Sırada bekliyor…')

    stream.release[0]()
    await Promise.resolve()
    await Promise.resolve()
    expect(stream.started).toEqual([1, 2, 3])
  })
})
