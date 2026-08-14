import { apiFetch } from './client'

/** İndeksleme işi (backend IndexingJobOut ile birebir). */
export interface IndexingJob {
  id: number
  course_id: number
  material_id: number | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  progress: number
  error: string | null
  created_at: string
  updated_at: string
}

export const indexingApi = {
  enqueue: (materialId: number) =>
    apiFetch<IndexingJob>(`/materials/${materialId}/index`, { method: 'POST' }),
  listByCourse: (courseId: number) =>
    apiFetch<IndexingJob[]>(`/courses/${courseId}/indexing-jobs`),
}
