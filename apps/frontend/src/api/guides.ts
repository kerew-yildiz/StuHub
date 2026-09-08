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

/** 422 hata gövdesinden Türkçe `detail` mesajını çıkarır. */
async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) return body.detail
  } catch {
    // gövde JSON değilse fallback mesajı kullan
  }
  return fallback
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
    throw new Error(await readErrorDetail(response, 'Rehber üretilemedi. Lütfen tekrar deneyin.'))
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

// ── Karşılaştırma tablosu (Plan #24) + terim sözlüğü (Plan #29) ────────────

/** Karşılaştırma rehberinin `kind` değeri (backend `COMPARISON_KIND`). */
export const COMPARISON_KIND = 'comparison'

/** Bir ikilideki tek fark satırı: ölçüt + iki kavramın o ölçütteki durumu. */
export interface ComparisonDifference {
  aspect: string
  a: string
  b: string
}

/** İki kavramın karşılaştırması. */
export interface ComparisonPair {
  a: string
  b: string
  similarities: string[]
  differences: ComparisonDifference[]
  /** Öğrencilerin bu ikilide en sık karıştırdığı nokta. */
  confusion: string
}

/** Karşılaştırma içeriği (backend `content_json`). */
export interface ComparisonContent {
  concepts: string[]
  pairs: ComparisonPair[]
}

/** Karşılaştırma rehberi (backend ile birebir). */
export interface ComparisonGuide {
  id: number
  kind: 'comparison'
  content_json: ComparisonContent
  created_at: string
}

/** Sözlük kaydı — tanım ve ilk geçiş bilgisi notun markdown metninden çıkarılır. */
export interface GlossaryEntry {
  term: string
  definition: string
  /** Terimin ilk geçtiği bölüm (hiçbir notta geçmiyorsa null). */
  chapter_id: number | null
  chapter_title: string | null
  note_id: number | null
  /** İlk geçişin not metnindeki karakter konumu. */
  position: number | null
  /** İlk geçişin altında bulunduğu markdown başlığı. */
  heading: string | null
}

/** Seçilen kavramların karşılaştırma tablosunu üretir (POST /courses/{id}/compare; LLM). */
export async function generateComparison(
  courseId: number,
  concepts: string[],
): Promise<GenerateGuideResult> {
  const response = await authFetch(`/courses/${courseId}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ concepts }),
  })
  if (!response.ok) {
    throw new Error(
      await readErrorDetail(response, 'Karşılaştırma üretilemedi. Lütfen tekrar deneyin.'),
    )
  }
  return (await response.json()) as GenerateGuideResult
}

/** Kayıtlı karşılaştırma tablosunu döndürür (GET /courses/{id}/guides?kind=comparison). */
export async function getComparison(courseId: number): Promise<ComparisonGuide | null> {
  try {
    const response = await authFetch(`/courses/${courseId}/guides?kind=${COMPARISON_KIND}`)
    if (!response.ok) return null
    return (await response.json()) as ComparisonGuide | null
  } catch {
    return null
  }
}

/** Ders terim sözlüğünü döndürür (GET /courses/{id}/glossary; alfabetik, LLM yok). */
export async function getGlossary(courseId: number): Promise<GlossaryEntry[]> {
  const response = await authFetch(`/courses/${courseId}/glossary`)
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, 'Terim sözlüğü alınamadı.'))
  }
  return (await response.json()) as GlossaryEntry[]
}
