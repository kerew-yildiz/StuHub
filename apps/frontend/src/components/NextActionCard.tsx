import { useEffect, useState } from 'react'

import { fetchNextAction, type NextAction, type NextActionKind } from '../api/nextAction'
import { listErrors } from '../api/errors'
import { CircleAlert } from 'lucide-react'

export interface NextActionCardProps {
  courseId: number
  /** `action='cards'` tıklanınca `flashcard_sets.id` ile çağrılır — sayfaya bağlama çağıran tarafın işi. */
  onOpenCards?: (setId: number) => void
  /** `action='read_chapter'` ve `action='error_quiz'` tıklanınca `chapters.id` ile çağrılır. */
  onOpenChapter?: (chapterId: number) => void
}

const BUTTON_LABEL: Record<Exclude<NextActionKind, 'none'>, string> = {
  cards: 'Kartları tekrarla',
  error_quiz: 'Kurtarma turu başlat',
  read_chapter: 'Bölümü oku',
}

/** Dersin tek karar kartı — "bugün ne çalışsam?" (Plan #13, deterministik, LLM YOK).
 *
 * Tek buton, öneriyi gerçek çalışma yüzeyine bağlar: `cards` → kart seti,
 * `read_chapter` → bölüm, `error_quiz` → hatanın yaşandığı bölüm (kurtarma = eksik
 * kalan konuya dönmek; ürün turu DEĞİL). Yönlendirmenin kendisi bu bileşenin dışında
 * (çağıran sayfa) yapılır; hedefi olmayan ya da hedefi bağlanmamış öneride buton
 * gizlenir — sessiz/boş tıklama olmaz. */
export function NextActionCard({ courseId, onOpenCards, onOpenChapter }: NextActionCardProps) {
  const [action, setAction] = useState<NextAction | null>(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setAction(null)
    setError('')
    setInfo('')
    fetchNextAction(courseId)
      .then((result) => {
        if (!cancelled) setAction(result)
      })
      .catch(() => {
        if (!cancelled) setError('Öneri alınamadı. Lütfen tekrar deneyin.')
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  // Sıkıntı #1: kendi panelini sarmalamaz — zaten bir feature-card içinde render
  // edilir; nested glass-panel (iç içe kart) yasak (yönerge §5).
  if (error) {
    return (
      <div className="flex items-center gap-2 text-sm text-stuhub-error">
        <CircleAlert size={20} aria-hidden="true" />
        {error}
      </div>
    )
  }

  if (action === null) {
    return (
      <div className="text-sm text-stuhub-text-muted">Öneri hazırlanıyor…</div>
    )
  }

  // Buton yalnızca hedefi VE hedefi açacak bağlama sahipse görünür.
  const clickable =
    action.action === 'cards'
      ? action.target_id !== null && Boolean(onOpenCards)
      : action.action === 'read_chapter'
        ? action.target_id !== null && Boolean(onOpenChapter)
        : action.action === 'error_quiz'
          ? Boolean(onOpenChapter)
          : false
  const buttonLabel = action.action === 'none' ? null : BUTTON_LABEL[action.action]

  async function handleClick() {
    if (action === null || busy) return
    setInfo('')
    if (action.action === 'cards' && action.target_id !== null) {
      onOpenCards?.(action.target_id)
      return
    }
    if (action.action === 'read_chapter' && action.target_id !== null) {
      onOpenChapter?.(action.target_id)
      return
    }
    if (action.action !== 'error_quiz') return

    // `error_quiz` önerisinde hedef bölüm öneri yanıtında YOK (backend yalnız konu
    // adını verir, target_id=null). Tekrarlayan hatanın bölümü hata günlüğünden
    // çözülür: backend'in konu seçimiyle aynı liste (only_repeated) ve aynı sıra —
    // ilk kayıt (en yeni) önerilen konudur.
    setBusy(true)
    try {
      const entries = await listErrors(courseId, { onlyRepeated: true })
      const chapterId = entries[0]?.chapter_id ?? null
      if (chapterId === null) {
        setInfo('Bu konuya bağlı bir bölüm yok; hatalarını dersin "Hatalarım" görünümünden tekrar çalışabilirsin.')
        return
      }
      onOpenChapter?.(chapterId)
    } catch {
      setInfo('Kurtarma turu başlatılamadı. Lütfen tekrar deneyin.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col items-start justify-center gap-3 self-stretch">
      {/* Kart kimliği ikonu kart başlığında (feature-card__top) — içerikteki ikinci
          ikon aynı Crosshair'i iki kez gösteriyordu (çift ikon). */}
      <p className="text-sm text-stuhub-text">{action.reason}</p>
      {clickable && buttonLabel && (
        <button type="button" className="btn-primary" onClick={handleClick} disabled={busy}>
          {busy ? 'Hazırlanıyor…' : buttonLabel}
        </button>
      )}
      {info && <p className="text-sm text-stuhub-text-secondary">{info}</p>}
    </div>
  )
}

export default NextActionCard
