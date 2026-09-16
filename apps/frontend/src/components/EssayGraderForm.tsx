import { useEffect, useState } from 'react'

import { gradeEssay, listEssays, type EssayGrade, type EssayRecord } from '../api/essays'

interface EssayGraderFormProps {
  courseId: number
}

/** Skoru semantik renkle işaretler (yeşil/sarı/kırmızı). */
function scoreTone(score: number): string {
  if (score >= 70) return 'text-stuhub-success'
  if (score >= 50) return 'text-stuhub-warning'
  return 'text-stuhub-error'
}

const TEXTAREA_CLASS =
  'w-full rounded-control border border-stuhub-border bg-stuhub-glass-2 px-3 py-2 text-sm text-stuhub-text outline-none transition-colors duration-[var(--duration-micro)] placeholder:text-stuhub-text-secondary focus:border-stuhub-accent'

/** Ödev değerlendirme formu — AI puanlama + geçmiş listesi (Faz V2.5). */
export function EssayGraderForm({ courseId }: EssayGraderFormProps) {
  const [instructions, setInstructions] = useState('')
  const [rubric, setRubric] = useState('')
  const [userText, setUserText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<EssayGrade | null>(null)
  const [history, setHistory] = useState<EssayRecord[]>([])

  useEffect(() => {
    let cancelled = false
    void listEssays(courseId)
      .then((records) => {
        if (!cancelled) setHistory(records)
      })
      .catch(() => {
        // geçmiş alınamazsa sessizce geç
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!instructions.trim() || !userText.trim()) {
      setError('Ödev talimatı ve ödev metni zorunludur.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const grade = await gradeEssay(courseId, instructions.trim(), rubric, userText)
      setResult(grade)
      setHistory(await listEssays(courseId))
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Ödev değerlendirilemedi. Lütfen tekrar deneyin.',
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
            <label htmlFor="essay-instructions" className="mb-1 block text-sm font-medium">
              Ödev talimatı
            </label>
            <textarea
              id="essay-instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              placeholder="Ödevin ne istediğini yaz (örn. 'Hücre bölünmesini açıklayan bir kompozisyon')"
              className={TEXTAREA_CLASS}
            />
          </div>
          <div>
            <label htmlFor="essay-rubric" className="mb-1 block text-sm font-medium">
              Değerlendirme ölçütleri (opsiyonel)
            </label>
            <textarea
              id="essay-rubric"
              value={rubric}
              onChange={(e) => setRubric(e.target.value)}
              rows={3}
              placeholder="Örn. 'İçerik doğruluğu (40), dil ve anlatım (30), yapı (30)'"
              className={TEXTAREA_CLASS}
            />
          </div>
          <div>
            <label htmlFor="essay-text" className="mb-1 block text-sm font-medium">
              Ödev metni
            </label>
            <textarea
              id="essay-text"
              value={userText}
              onChange={(e) => setUserText(e.target.value)}
              rows={8}
              placeholder="Değerlendirilecek metni buraya yapıştır"
              className={TEXTAREA_CLASS}
            />
          </div>
        </div>

        {error && <p className="mt-3 text-sm text-stuhub-error">{error}</p>}

        <div className="mt-4">
          <button
            type="submit"
            disabled={busy}
            className="btn-primary"
          >
            {busy ? 'Değerlendiriliyor…' : 'Değerlendir'}
          </button>
        </div>
      </form>

      {result && (
        <div className="mt-6 glass-panel p-6">
          <div className="flex items-baseline gap-2">
            <span className={`text-4xl font-semibold ${scoreTone(result.score)}`}>
              {result.score}
            </span>
            <span className="text-sm text-stuhub-text-secondary">/ 100</span>
          </div>

          {result.criteria.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-stuhub-text-secondary">Ölçütler</h3>
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="border-b border-stuhub-border text-left text-xs text-stuhub-text-secondary">
                    <th className="py-2 pr-4 font-medium">Ölçüt</th>
                    <th className="py-2 pr-4 font-medium">Puan</th>
                    <th className="py-2 font-medium">Yorum</th>
                  </tr>
                </thead>
                <tbody>
                  {result.criteria.map((criterion) => (
                    <tr key={criterion.name} className="border-b border-stuhub-border align-top">
                      <td className="py-2 pr-4 font-medium">{criterion.name}</td>
                      <td className="py-2 pr-4 text-stuhub-text-secondary">
                        {criterion.score} / {criterion.max}
                      </td>
                      <td className="py-2">{criterion.comment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.strengths.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-stuhub-success">Güçlü Yönler</h3>
              <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
                {result.strengths.map((strength, index) => (
                  <li key={index}>{strength}</li>
                ))}
              </ul>
            </div>
          )}

          {result.weaknesses.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-stuhub-error">Zayıf Yönler</h3>
              <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
                {result.weaknesses.map((weakness, index) => (
                  <li key={index}>{weakness}</li>
                ))}
              </ul>
            </div>
          )}

          {result.quotes.length > 0 && (
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-stuhub-text-secondary">Alıntılar</h3>
              <div className="mt-2 space-y-3">
                {result.quotes.map((quote, index) => (
                  <div key={index} className="rounded-control bg-stuhub-glass-2 p-3">
                    <blockquote className="border-l-2 border-stuhub-accent pl-3 italic">
                      “{quote.text}”
                    </blockquote>
                    {quote.comment && (
                      <p className="mt-1 text-sm text-stuhub-text-secondary">{quote.comment}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-8">
        <h3 className="text-sm font-semibold text-stuhub-text-secondary">Geçmiş Değerlendirmeler</h3>
        {history.length === 0 ? (
          <p className="mt-2 text-sm text-stuhub-text-secondary">Henüz değerlendirme yok.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {history.map((record) => (
              <li
                key={record.id}
                className="glass-panel-subtle flex items-center justify-between rounded-control px-4 py-2 text-sm"
              >
                <span className="shrink-0 font-medium">{record.score} puan</span>
                <span className="min-w-0 flex-1 truncate px-4 text-stuhub-text-secondary">
                  {record.prompt}
                </span>
                <span className="shrink-0 text-stuhub-text-secondary">
                  {new Date(record.created_at).toLocaleDateString('tr-TR')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
