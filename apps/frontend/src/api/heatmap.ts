import { apiFetch } from './client'

/** Tek konunun ısı haritası satırı (backend `TopicHeat` ile birebir). */
export interface TopicHeat {
  topic: string
  /** 0..1 quiz doğruluğu — hiç deneme yoksa null. */
  quiz_accuracy: number | null
  /** 0..1 kart tutma oranı ("good"+"easy" / puanlanmış tekrar) — tekrar yoksa null. */
  card_retention: number | null
  /** 0..1 birleşik zayıflık; 1 = en zayıf. Hiçbir sinyalde veri yoksa null. */
  weakness_score: number | null
  /** Skorun dayandığı toplam gözlem sayısı (cevap + tekrar). */
  sample_size: number
}

/** Ders bazlı ısı haritası (backend `HeatmapOut` ile birebir). */
export interface CourseHeatmap {
  course_id: number
  /** Sinyal ağırlıkları: quiz / card (chat sinyali kaldırıldı, 2026-09-19). */
  weights: Record<string, number>
  /** Zayıftan güçlüye sıralı; skoru olmayan konular sonda. */
  topics: TopicHeat[]
}

/** Dersin zayıf konu ısı haritasını çeker (Plan #18). */
export function getHeatmap(courseId: number): Promise<CourseHeatmap> {
  return apiFetch<CourseHeatmap>(`/courses/${courseId}/heatmap`)
}
