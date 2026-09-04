import { authFetch } from './client'

/** Rehber türü (backend `kind` parametresi ile birebir). */
export type GuideKind = 'summary' | 'concept_map'

/** Rehber hedefi: chapter veya course. */
export type GuideScope = 'chapter' | 'course'

/** Özet içeriği (backend `content_json`). */
export interface SummaryContent {
  summary_md: string
  key_terms: string[]
  exam_focus: string[]
}

/** Kavram haritası düğümü. */
export interface ConceptNode {
  id: string
  label: string
  importance: number
}

/** Kavram haritası kenarı (from → to). */
export interface ConceptEdge {
  from: string
  to: string
  label?: string
}

/** Kavram haritası içeriği. */
export interface ConceptMapContent {
  nodes: ConceptNode[]
  edges: ConceptEdge[]
}

/** Özet rehberi (backend ile birebir). */
export interface SummaryGuide {
  id: number
  kind: 'summary'
  content_json: SummaryContent
  created_at: string
}

/** Kavram haritası rehberi (backend ile birebir). */
export interface ConceptMapGuide {
  id: number
  kind: 'concept_map'
  content_json: ConceptMapContent
  created_at: string
}

export type Guide = SummaryGuide | ConceptMapGuide

/** generateGuide dönüşü (backend meta kaydı). */
export interface GenerateGuideResult {
  id: number
  course_id: number | null
  chapter_id: number | null
  kind: string
}

function scopeBase(scope: GuideScope, id: number): string {
  return scope === 'chapter' ? `chapters/${id}` : `courses/${id}`
}

/** Rehber üretimini tetikler (POST …/guide?kind=…; LLM çağrısı senkrondur). */
export async function generateGuide(
  scope: GuideScope,
  id: number,
  kind: GuideKind,
): Promise<GenerateGuideResult> {
  const response = await authFetch(`/${scopeBase(scope, id)}/guide?kind=${kind}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Rehber üretilemedi. Lütfen tekrar deneyin.')
  }
  return (await response.json()) as GenerateGuideResult
}

/** Kayıtlı rehberi döndürür (GET …/guides?kind=…; yoksa null). */
export async function getGuide(
  scope: GuideScope,
  id: number,
  kind: GuideKind,
): Promise<Guide | null> {
  try {
    const response = await authFetch(`/${scopeBase(scope, id)}/guides?kind=${kind}`)
    if (!response.ok) return null
    return (await response.json()) as Guide
  } catch {
    return null
  }
}
