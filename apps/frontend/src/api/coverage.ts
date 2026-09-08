import { authFetch } from './client'

/** Tek ders kitabı için kapsama kırılımı (backend MaterialCoverage ile birebir). */
export interface MaterialCoverage {
  material_id: number
  filename: string
  total_pages: number
  covered_pages: number[]
  /** Kapsanmayan bitişik sayfa aralıkları, kapalı: [[12, 18], [40, 41]] */
  uncovered_ranges: number[][]
  coverage_ratio: number
}

/** Chapter kaynak kapsama özeti (backend CoverageOut ile birebir). */
export interface ChapterCoverage {
  chapter_id: number
  note_id: number | null
  total_pages: number
  covered_pages: number[]
  uncovered_ranges: number[][]
  coverage_ratio: number
  materials: MaterialCoverage[]
  /** Notta atıf verilen ama bu derste artık var olmayan materyal id'leri — doluysa
   * kapsama oranı güvenilmezdir (2026-09-08 kritik incelemede tespit edildi). */
  orphaned_source_ids: number[]
}

/** Notun kitabın hangi sayfalarını kaynak olarak kullandığı (GET /api/chapters/{id}/coverage).
 *
 * Alanları normalize eder — eski bir önbelleğe alınmış yanıt (ör. `orphaned_source_ids`
 * backend'e eklenmeden önce servis edilmiş) `undefined` dizilerle geldiğinde bileşenlerin
 * `.length` erişiminde çökmesini önler (2026-09-08 canlı bulgu: CoverageIndicator crash). */
export async function getCoverage(chapterId: number): Promise<ChapterCoverage | null> {
  const response = await authFetch(`/chapters/${chapterId}/coverage`)
  if (!response.ok) return null
  const data = (await response.json()) as Partial<ChapterCoverage>
  return {
    chapter_id: data.chapter_id ?? chapterId,
    note_id: data.note_id ?? null,
    total_pages: data.total_pages ?? 0,
    covered_pages: data.covered_pages ?? [],
    uncovered_ranges: data.uncovered_ranges ?? [],
    coverage_ratio: data.coverage_ratio ?? 0,
    materials: (data.materials ?? []).map((material) => ({
      material_id: material.material_id,
      filename: material.filename,
      total_pages: material.total_pages ?? 0,
      covered_pages: material.covered_pages ?? [],
      uncovered_ranges: material.uncovered_ranges ?? [],
      coverage_ratio: material.coverage_ratio ?? 0,
    })),
    orphaned_source_ids: data.orphaned_source_ids ?? [],
  }
}
