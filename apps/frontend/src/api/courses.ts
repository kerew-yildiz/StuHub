import { apiFetch } from './client'

/** Ders (backend CourseOut ile birebir). */
export interface Course {
  id: number
  term_id: number
  name: string
  instructor: string | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export interface CourseInput {
  name: string
  instructor?: string | null
  metadata_json?: Record<string, unknown>
}

export const coursesApi = {
  listByTerm: (termId: number) => apiFetch<Course[]>(`/terms/${termId}/courses`),
  get: (id: number) => apiFetch<Course>(`/courses/${id}`),
  create: (termId: number, input: CourseInput) =>
    apiFetch<Course>(`/terms/${termId}/courses`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  update: (id: number, input: CourseInput) =>
    apiFetch<Course>(`/courses/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  remove: (id: number) => apiFetch<void>(`/courses/${id}`, { method: 'DELETE' }),
}
