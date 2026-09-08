import { CheckCircle, XCircle } from '@phosphor-icons/react'
import { useState } from 'react'

import { draftReview, type DraftFeedback } from '../api/essays'

export interface EssayDraftCoachProps {
  courseId: number
}

const TEXTAREA_CLASS =
  'w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent'

/** Ödev taslak koçu — PUAN VERMEZ, yalnızca tez/kanıt/zayıf bölüm geri bildirimi verir
 * (Plan #41). Son teslimden önce öğrenciyi yönlendirmek için tasarlandı. */
export function EssayDraftCoach({ courseId }: EssayDraftCoachProps) {
  const [instructions, setInstructions] = useState('')
  const [rubric, setRubric] = useState('')
  const [userText, setUserText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState<DraftFeedback | null>(null)

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!instructions.trim() || !userText.trim()) {
      setError('Ödev talimatı ve taslak metni zorunludur.')
      return
    }
    setBusy(true)
    setError('')
    try {
      setFeedback(await draftReview(courseId, instructions.trim(), rubric, userText))
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Taslak değerlendirilemedi. Lütfen tekrar deneyin.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="glass-panel p-6">
        <div className="space-y-4">
          <div>
            <label htmlFor="draft-instructions" className="mb-1 block text-sm font-medium">
              Ödev talimatı
            </label>
            <textarea
              id="draft-instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              placeholder="Ödevin ne istediğini yaz"
              className={TEXTAREA_CLASS}
            />
          </div>
          <div>
            <label htmlFor="draft-rubric" className="mb-1 block text-sm font-medium">
              Değerlendirme ölçütleri (opsiyonel)
            </label>
            <textarea
              id="draft-rubric"
              value={rubric}
              onChange={(e) => setRubric(e.target.value)}
              rows={2}
              className={TEXTAREA_CLASS}
            />
          </div>
          <div>
            <label htmlFor="draft-text" className="mb-1 block text-sm font-medium">
              Taslak metin
            </label>
            <textarea
              id="draft-text"
              value={userText}
              onChange={(e) => setUserText(e.target.value)}
              rows={8}
              placeholder="Henüz bitmemiş taslağını buraya yapıştır — puan verilmez, yalnızca yönlendirme alırsın"
              className={TEXTAREA_CLASS}
            />
          </div>
        </div>

        {error && <p className="mt-3 text-sm text-stuhub-error">{error}</p>}

        <div className="mt-4">
          <button type="submit" disabled={busy} className="btn-primary">
            {busy ? 'Değerlendiriliyor…' : 'Geri Bildirim Al'}
          </button>
        </div>
      </form>

      {feedback && (
        <div className="mt-6 glass-panel p-6">
          <div className="flex items-center gap-2">
            {feedback.has_thesis ? (
              <CheckCircle size={20} className="text-stuhub-success" />
            ) : (
              <XCircle size={20} className="text-stuhub-error" />
            )}
            <h3 className="text-sm font-semibold">Tez / Ana İddia</h3>
          </div>
          <p className="mt-1 text-sm text-stuhub-text-secondary">{feedback.thesis_feedback}</p>

          <div className="mt-4 flex items-center gap-2">
            {feedback.evidence_linked ? (
              <CheckCircle size={20} className="text-stuhub-success" />
            ) : (
              <XCircle size={20} className="text-stuhub-error" />
            )}
            <h3 className="text-sm font-semibold">Kanıt Bağlantısı</h3>
          </div>
          <p className="mt-1 text-sm text-stuhub-text-secondary">{feedback.evidence_feedback}</p>

          {feedback.weak_sections.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-stuhub-warning">Zayıf Bölümler</h3>
              <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
                {feedback.weak_sections.map((section, index) => (
                  <li key={index}>{section}</li>
                ))}
              </ul>
            </div>
          )}

          {feedback.next_steps.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-stuhub-text-secondary">Sonraki Adımlar</h3>
              <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
                {feedback.next_steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default EssayDraftCoach
