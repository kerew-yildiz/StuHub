import { apiFetch } from './client'

/** Guide slide (backend SlideOut ile birebir). */
export interface Slide {
  id: number
  chapter_id: number
  material_id: number | null
  slide_no: number
  content_text: string | null
}

export const slidesApi = {
  upload: (chapterId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiFetch<Slide[]>(`/chapters/${chapterId}/slides`, {
      method: 'POST',
      body: form,
    })
  },
  listByChapter: (chapterId: number) =>
    apiFetch<Slide[]>(`/chapters/${chapterId}/slides`),
  remove: (slideId: number) => apiFetch<void>(`/slides/${slideId}`, { method: 'DELETE' }),
}
