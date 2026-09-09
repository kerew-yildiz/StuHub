import { create } from 'zustand'

import {
  answerFeed,
  fetchChapterMastery,
  fetchCourseMastery,
  fetchFeed,
  saveQuestion,
  skipFeed,
  unsaveQuestion,
  type AnswerResult,
  type FeedQuestion,
  type Mastery,
} from '../api/feed'

/** İstemci tamponundaki azami cevaplanmamış/atlanmamış soru sayısı ("sırada" bekleyen).
 * Kullanıcı bir soruyla etkileşime girdikçe (cevap/atla) tampon bu sayının altına iner
 * ve arka planda tekrar bu sayıya tamamlanır — sınırsız önden yükleme YOK. */
export const MAX_BUFFER = 5
/** Havuz boşken ilk yeniden deneme gecikmesi. */
export const RETRY_BASE_MS = 3000
/** Üstel geri çekilmenin üst sınırı — sonsuz sıkı döngü yok. */
export const RETRY_MAX_MS = 30000

export type FeedPhase = 'idle' | 'loading' | 'ready' | 'waiting' | 'error'

interface FeedState {
  courseId: number | null
  /** `null` = ders geneli; verilirse akış bu chapter'a daraltılır. */
  chapterId: number | null
  /** Çekilmiş sorular; hiç kısaltılmaz (geri kaydırma çalışsın). */
  queue: FeedQuestion[]
  /** Aktif kartın kuyruk indeksi; `queue.length` = kuyruk tükendi (kuyruk sonu kartı). */
  index: number
  /** feed_id → sunucudan gelen değerlendirme (yalnızca cevaplanmışlar). */
  answers: Record<number, AnswerResult>
  /** feed_id → kullanıcının seçtiği şık indeksi (kart unmount olsa da korunur). */
  selections: Record<number, number>
  /** feed_id → true: kullanıcı bu soruyla etkileşime girdi (cevapladı ya da atladı).
   * Etkileşime girilmemiş aktif soru varken sıradaki soruya geçilemez. */
  interacted: Record<number, true>
  phase: FeedPhase
  /** Kuyruk/parti hatası (Türkçe); kuyruk korunur. */
  error: string | null
  /** Cevap gönderimi hatası (Türkçe) — kartı boşaltmaz. */
  answerError: string | null
  /** Cevap gönderimi sürerken kart kilitli (optimistik güncelleme YOK). */
  submitting: boolean
  poolReady: number
  generating: boolean
  /** Aktif scope (courseId/chapterId) için ustalık ilerlemesi; alınamadıysa `null`. */
  mastery: Mastery | null
}

interface FeedStore extends FeedState {
  /** Ders (+opsiyonel chapter) için ilk partiyi çeker; aynı scope için tekrar çağrılırsa
   * yalnızca tamponu tazeler. */
  loadInitial: (courseId: number, chapterId?: number | null) => Promise<void>
  /** Görünür kartı bildirir (IntersectionObserver / klavye) — prefetch tetikleyicisi. */
  setIndex: (index: number) => void
  /** Kullanıcı isteğiyle yeniden dene (hata durumundaki düğme). */
  retry: () => Promise<void>
  submitAnswer: (feedId: number, selectedIndex: number, elapsedMs: number) => Promise<void>
  /** Aktif soruyu cevaplamadan geçer (sunucuya bildirir, kartı ilerletmez). */
  skipQuestion: (feedId: number) => Promise<void>
  /** Kaydet/kaydı kaldır — optimistik günceller, sunucu hatasında geri alır. */
  toggleSave: (feedId: number) => Promise<void>
  /** Bileşen ayrılırken bekleyen yeniden denemeyi iptal eder (arka planda yoklama kalmaz). */
  suspend: () => void
  /** Tüm durumu sıfırlar (test / ders değişimi). */
  reset: () => void
}

const initialState: FeedState = {
  courseId: null,
  chapterId: null,
  queue: [],
  index: 0,
  answers: {},
  selections: {},
  interacted: {},
  phase: 'idle',
  error: null,
  answerError: null,
  submitting: false,
  poolReady: 0,
  generating: false,
  mastery: null,
}

/* Prefetch mekaniği bilinçli olarak store state'i DIŞINDA: bunlar render'ı
 * etkilemeyen eşzamanlılık kilitleri, state'e konsa her tetiklemede gereksiz
 * yeniden render üretirdi. */
let inFlight = false
let retryTimer: number | null = null
let retryDelay = RETRY_BASE_MS
/** Sıfırlama/ders değişiminde uçuşta kalan yanıtları geçersiz kılan sayaç. */
let generation = 0

function cancelRetry(): void {
  if (retryTimer !== null) {
    window.clearTimeout(retryTimer)
    retryTimer = null
  }
}

export const useFeedStore = create<FeedStore>((set, get) => {
  /** Havuz boşken üstel geri çekilmeli tek bekleyen yeniden deneme. */
  const scheduleRetry = (): void => {
    if (retryTimer !== null) return
    const delay = retryDelay
    retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS)
    const gen = generation
    retryTimer = window.setTimeout(() => {
      retryTimer = null
      if (gen !== generation) return
      void loadBatch()
    }, delay)
  }

  /** Tek parti çeker (`limit` = eksik olan tampon miktarı). Aynı anda EN FAZLA BİR çağrı
   * (in-flight kilidi). */
  const loadBatch = async (limit: number = MAX_BUFFER): Promise<void> => {
    const { courseId, chapterId } = get()
    if (courseId === null || inFlight) return
    inFlight = true
    const gen = generation
    try {
      const batch = await fetchFeed(courseId, limit, chapterId ?? undefined)
      if (gen !== generation) return

      if (batch.items.length === 0) {
        set({
          poolReady: batch.pool_ready,
          generating: batch.generating,
          error: null,
          phase: get().queue.length > 0 && !batch.generating ? 'ready' : 'waiting',
        })
        if (batch.generating) scheduleRetry()
        return
      }

      retryDelay = RETRY_BASE_MS
      set((state) => {
        const known = new Set(state.queue.map((q) => q.feed_id))
        const fresh = batch.items.filter((q) => !known.has(q.feed_id))
        return {
          queue: fresh.length > 0 ? [...state.queue, ...fresh] : state.queue,
          poolReady: batch.pool_ready,
          generating: batch.generating,
          phase: 'ready',
          error: null,
        }
      })
    } catch {
      if (gen !== generation) return
      // Kuyruk korunur; yalnızca hata durumu yayınlanır.
      set({ phase: 'error', error: 'Sorular alınamadı. Bağlantını kontrol et.' })
      scheduleRetry()
    } finally {
      inFlight = false
    }
  }

  /** Aktif scope için ustalık ilerlemesini çeker; en iyi çaba — hata sessizce yutulur
   * (çubuk zaten `mastery === null`/`total === 0` iken gizlenir). */
  const loadMastery = async (): Promise<void> => {
    const { courseId, chapterId } = get()
    if (courseId === null) return
    const gen = generation
    try {
      const mastery = chapterId !== null
        ? await fetchChapterMastery(chapterId)
        : await fetchCourseMastery(courseId)
      if (gen !== generation) return
      set({ mastery })
    } catch {
      // Ustalık en iyi çaba: kullanıcı akışı hata yüzünden durmaz.
    }
  }

  /** Tampon (aktif karttan itibaren henüz etkileşim görmemiş soru sayısı) `MAX_BUFFER`
   * altındaysa eksik kadarını arka planda çeker. */
  const ensureBuffer = (): void => {
    const { courseId, queue, index, interacted } = get()
    if (courseId === null) return
    const ahead = queue.slice(index).filter((q) => !interacted[q.feed_id]).length
    const deficit = MAX_BUFFER - ahead
    if (deficit <= 0) return
    void loadBatch(deficit)
  }

  return {
    ...initialState,

    loadInitial: async (courseId, chapterId = null) => {
      const state = get()
      if (state.courseId === courseId && state.chapterId === chapterId && state.phase !== 'idle') {
        // Aynı scope: durumu koru, yalnızca tamponu tazele (bileşen yeniden bağlandı).
        ensureBuffer()
        return
      }
      cancelRetry()
      generation += 1
      inFlight = false
      retryDelay = RETRY_BASE_MS
      set({ ...initialState, courseId, chapterId, phase: 'loading' })
      await Promise.all([loadBatch(), loadMastery()])
    },

    setIndex: (index) => {
      const { queue, index: current, interacted } = get()
      let next = Math.max(0, Math.min(index, queue.length))
      if (next > current) {
        // İleri geçiş: aktif soruyla (varsa) etkileşime girilmeden sıradaki
        // soru gösterilmez — cevaplama/atlama bunu serbest bırakır.
        const activeQuestion = queue[current]
        if (activeQuestion && !interacted[activeQuestion.feed_id]) {
          next = current
        }
      }
      if (next !== current) set({ index: next, answerError: null })
      ensureBuffer()
    },

    retry: async () => {
      cancelRetry()
      retryDelay = RETRY_BASE_MS
      set({ error: null, phase: get().queue.length > 0 ? 'ready' : 'loading' })
      const { queue, index, interacted } = get()
      const ahead = queue.slice(index).filter((q) => !interacted[q.feed_id]).length
      await loadBatch(Math.max(1, MAX_BUFFER - ahead))
    },

    submitAnswer: async (feedId, selectedIndex, elapsedMs) => {
      if (get().submitting || get().answers[feedId]) return
      set((state) => ({
        submitting: true,
        answerError: null,
        selections: { ...state.selections, [feedId]: selectedIndex },
      }))
      try {
        const result = await answerFeed(feedId, selectedIndex, elapsedMs)
        set((state) => ({
          answers: { ...state.answers, [feedId]: result },
          interacted: { ...state.interacted, [feedId]: true },
          submitting: false,
        }))
        ensureBuffer()
        // Konu ustalığı yalnızca doğru cevaplarda değişebilir — yanlışta boşuna çekilmez.
        if (result.correct) void loadMastery()
      } catch {
        set({ submitting: false, answerError: 'Cevap gönderilemedi. Lütfen tekrar deneyin.' })
      }
    },

    skipQuestion: async (feedId) => {
      const courseId = get().courseId
      if (courseId === null) return
      // Atlama = etkileşim: hemen işaretlenir (sunucu isteği en iyi çaba, sonucu beklemez).
      set((state) => ({ interacted: { ...state.interacted, [feedId]: true } }))
      ensureBuffer()
      try {
        await skipFeed(courseId, feedId)
      } catch {
        // Atlama en iyi çaba: kullanıcı akışı hata yüzünden durmaz.
      }
    },

    toggleSave: async (feedId) => {
      const question = get().queue.find((q) => q.feed_id === feedId)
      if (!question) return
      const wasSaved = question.saved
      set((state) => ({
        queue: state.queue.map((q) => (q.feed_id === feedId ? { ...q, saved: !wasSaved } : q)),
      }))
      try {
        if (wasSaved) await unsaveQuestion(feedId)
        else await saveQuestion(feedId)
      } catch {
        // Sunucu isteği başarısız — optimistik güncelleme geri alınır.
        set((state) => ({
          queue: state.queue.map((q) => (q.feed_id === feedId ? { ...q, saved: wasSaved } : q)),
        }))
      }
    },

    suspend: () => {
      cancelRetry()
    },

    reset: () => {
      cancelRetry()
      generation += 1
      inFlight = false
      retryDelay = RETRY_BASE_MS
      set({ ...initialState })
    },
  }
})
