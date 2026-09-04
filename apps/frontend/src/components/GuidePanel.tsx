import { useEffect, useState } from 'react'

import { alertDialog } from '../stores/alertStore'

import {
  generateGuide,
  getGuide,
  type ConceptMapGuide,
  type GuideKind,
  type GuideScope,
  type SummaryGuide,
} from '../api/guides'
import { GuideView } from './GuideView'

interface GuidePanelProps {
  scope: GuideScope
  scopeId: number
}

const KIND_BUTTON_LABEL: Record<GuideKind, string> = {
  summary: 'Özet Üret',
  concept_map: 'Kavram Haritası',
}

const KIND_GENERATING_LABEL: Record<GuideKind, string> = {
  summary: 'Üretiliyor…',
  concept_map: 'Üretiliyor…',
}

/** Rehber paneli — özet + kavram haritası üretimi ve gösterimi (Faz V2.7). */
export function GuidePanel({ scope, scopeId }: GuidePanelProps) {
  const [summary, setSummary] = useState<SummaryGuide | null>(null)
  const [conceptMap, setConceptMap] = useState<ConceptMapGuide | null>(null)
  const [generating, setGenerating] = useState<GuideKind | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const [summaryGuide, conceptMapGuide] = await Promise.all([
        getGuide(scope, scopeId, 'summary'),
        getGuide(scope, scopeId, 'concept_map'),
      ])
      if (cancelled) return
      if (summaryGuide?.kind === 'summary') setSummary(summaryGuide)
      if (conceptMapGuide?.kind === 'concept_map') setConceptMap(conceptMapGuide)
    })()
    return () => {
      cancelled = true
    }
  }, [scope, scopeId])

  const handleGenerate = async (kind: GuideKind) => {
    setGenerating(kind)
    setError('')
    try {
      await generateGuide(scope, scopeId, kind)
      const guide = await getGuide(scope, scopeId, kind)
      if (!guide) {
        setError('Rehber bulunamadı. Lütfen tekrar deneyin.')
        return
      }
      if (guide.kind === 'summary') setSummary(guide)
      else setConceptMap(guide)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Rehber üretilemedi. Lütfen tekrar deneyin.'
      setError(message)
      void alertDialog(message)
    } finally {
      setGenerating(null)
    }
  }

  const renderSection = (
    kind: GuideKind,
    title: string,
    description: string,
    guide: SummaryGuide | ConceptMapGuide | null,
  ) => (
    <section>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-stuhub-text-secondary">{description}</p>
        </div>
        <button
          type="button"
          onClick={() => void handleGenerate(kind)}
          disabled={generating !== null}
          className="btn-primary"
        >
          {generating === kind ? KIND_GENERATING_LABEL[kind] : KIND_BUTTON_LABEL[kind]}
        </button>
      </div>
      {guide && (
        <div className="mt-4">
          <GuideView guide={guide} />
        </div>
      )}
    </section>
  )

  return (
    <div className="mt-8 space-y-10">
      {error && (
        <p role="alert" className="rounded-control bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
          {error}
        </p>
      )}
      {renderSection(
        'summary',
        'Özet',
        'İçerikten yapılandırılmış özet, anahtar terimler ve sınav odakları üretir.',
        summary,
      )}
      {renderSection(
        'concept_map',
        'Kavram Haritası',
        'Konuların ilişkilerini görsel bir haritaya döker.',
        conceptMap,
      )}
    </div>
  )
}
