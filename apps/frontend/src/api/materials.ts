import { apiFetch } from './client'

/** Materyal (backend MaterialOut ile birebir). */
export interface Material {
  id: number
  course_id: number
  type: 'textbook' | 'slides'
  filepath: string
  display_name: string
  extracted_text: string | null
  page_count: number | null
  vector_ns: string | null
  created_at: string
}

export const materialsApi = {
  listByCourse: (courseId: number) => apiFetch<Material[]>(`/courses/${courseId}/materials`),
  get: (id: number) => apiFetch<Material>(`/materials/${id}`),
  upload: (courseId: number, type: 'textbook' | 'slides', file: File) => {
    const form = new FormData()
    form.append('type', type)
    form.append('file', file)
    return apiFetch<Material>(`/courses/${courseId}/materials`, {
      method: 'POST',
      body: form,
    })
  },
  remove: (id: number) => apiFetch<void>(`/materials/${id}`, { method: 'DELETE' }),
}
