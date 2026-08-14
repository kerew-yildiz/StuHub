import { apiFetch } from './client'

/** Chapter (backend ChapterOut ile birebir). */
export interface Chapter {
  id: number
  course_id: number
  title: string
  created_at: string
}

export const chaptersApi = {
  listByCourse: (courseId: number) => apiFetch<Chapter[]>(`/courses/${courseId}/chapters`),
  create: (courseId: number, title: string) =>
    apiFetch<Chapter>(`/courses/${courseId}/chapters`, {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  remove: (id: number) => apiFetch<void>(`/chapters/${id}`, { method: 'DELETE' }),
}
