import { authFetch } from './client'

/** Takvim etkinliği — sınavlar exams'tan, ödev/kişisel notlar kullanıcıdan gelir.
 * kind 'exam'|'project' kullanıcı tarafından da eklenebilir (source: 'user'). */
export interface CalendarEvent {
  id: number
  course_id: number | null
  event_date: string
  kind: 'exam' | 'assignment' | 'custom' | 'project'
  title: string
  source: 'exam' | 'user'
  tags: string[]
}

export async function listCalendarEvents(
  start: string,
  end: string,
): Promise<CalendarEvent[]> {
  const response = await authFetch(
    `/calendar-events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
  )
  if (!response.ok) return []
  return (await response.json()) as CalendarEvent[]
}

export async function createCalendarEvent(input: {
  event_date: string
  kind: 'assignment' | 'custom' | 'exam' | 'project'
  title: string
  course_id?: number | null
  tags?: string[]
}): Promise<CalendarEvent | null> {
  const response = await authFetch('/calendar-events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!response.ok) return null
  return (await response.json()) as CalendarEvent
}

export async function deleteCalendarEvent(eventId: number): Promise<boolean> {
  const response = await authFetch(`/calendar-events/${eventId}`, { method: 'DELETE' })
  return response.ok
}
