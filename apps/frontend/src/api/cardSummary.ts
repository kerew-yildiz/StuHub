import { apiFetch } from './client'

/** Ders kartı hover rotation verisi — backend GET /courses/{id}/card-summary (§36). */
export interface NextExam {
  title: string
  exam_date: string
  days_left: number
}

export interface LastActivity {
  at: string
  kind: string
  label: string | null
}

export interface ChapterCardSummary {
  chapter_id: number
  topics_total: number
  topics_completed: number
  total_study_sec: number | null
  last_activity: string | null
}

export interface CourseCardSummary {
  course_id: number
  progress: number | null
  next_exam: NextExam | null
  total_study_sec: number
  last_activity: LastActivity | null
  completed_chapters: number
  total_chapters: number
  chapters: ChapterCardSummary[]
}

export function getCardSummary(courseId: number): Promise<CourseCardSummary> {
  return apiFetch<CourseCardSummary>(`/courses/${courseId}/card-summary`)
}
