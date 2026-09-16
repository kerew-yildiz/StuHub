import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MonthCalendar } from './MonthCalendar'

const { listCalendarEvents } = vi.hoisted(() => ({ listCalendarEvents: vi.fn() }))

vi.mock('../api/calendarEvents', () => ({
  listCalendarEvents,
  createCalendarEvent: vi.fn(),
  deleteCalendarEvent: vi.fn(),
}))
vi.mock('../api/courses', () => ({ coursesApi: { listByTerm: vi.fn().mockResolvedValue([]) } }))
vi.mock('../api/terms', () => ({ termsApi: { list: vi.fn().mockResolvedValue([]) } }))

/** `YYYY-AA-GG` — bileşenin toISODate'i ile aynı biçim (yerel tarih parçaları). */
function iso(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${m}-${d}`
}

/** Ayın son günü. Komşu ay hücresi olarak "Sonraki ay" grid'inde kalabilir —
 * popover'ın kapanmadığı asıl senaryo (eski hücre ay dışı, soluk kalıyordu). */
function lastDayOfThisMonth(): string {
  const now = new Date()
  return iso(new Date(now.getFullYear(), now.getMonth() + 1, 0))
}

/** Ayın ilk günü. "Önceki ay" grid'inin sonunda komşu hücre olarak kalabilir. */
function firstDayOfThisMonth(): string {
  const now = new Date()
  return iso(new Date(now.getFullYear(), now.getMonth(), 1))
}

/** Portal popover ölçümü — yükleme göstergesi de `role="status"` olduğu için
 * popover'a ÖZEL iki gözlemlenebilir kullanılır: kapatma düğmesi ve etkinlik başlığı. */
function popoverCloseButton(): HTMLElement | null {
  return screen.queryByRole('button', { name: 'Kapat' })
}

function renderWithEventOn(eventDate: string) {
  listCalendarEvents.mockResolvedValue([
    {
      id: 1,
      course_id: null,
      event_date: eventDate,
      kind: 'assignment',
      title: 'Deneme ödevi',
      source: 'user',
      tags: [],
    },
  ])
  // `courses={[]}`: ders/term fetch'i tetiklenmesin (prop truthy → effect erken çıkar).
  return render(<MonthCalendar courses={[]} />)
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MonthCalendar — portal popover', () => {
  it('güne hover popover açar, hücreden çıkışta kapatır', async () => {
    const eventDate = lastDayOfThisMonth()
    renderWithEventOn(eventDate)

    const cell = await screen.findByRole('gridcell', { name: /1 etkinlik/ })
    expect(cell).toHaveAttribute('data-iso', eventDate)

    fireEvent.mouseEnter(cell)
    expect(popoverCloseButton()).not.toBeNull()
    expect(screen.getByText('Deneme ödevi')).toBeInTheDocument()

    fireEvent.mouseLeave(cell, { relatedTarget: document.body })
    expect(popoverCloseButton()).toBeNull()
    expect(screen.queryByText('Deneme ödevi')).not.toBeInTheDocument()
  })

  it('"Sonraki ay" popover açıkken kapatır', async () => {
    renderWithEventOn(lastDayOfThisMonth())

    fireEvent.mouseEnter(await screen.findByRole('gridcell', { name: /1 etkinlik/ }))
    expect(popoverCloseButton()).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Sonraki ay' }))
    expect(popoverCloseButton()).toBeNull()
    expect(screen.queryByText('Deneme ödevi')).not.toBeInTheDocument()
  })

  it('"Önceki ay" popover açıkken kapatır', async () => {
    renderWithEventOn(firstDayOfThisMonth())

    fireEvent.mouseEnter(await screen.findByRole('gridcell', { name: /1 etkinlik/ }))
    expect(popoverCloseButton()).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Önceki ay' }))
    expect(popoverCloseButton()).toBeNull()
    expect(screen.queryByText('Deneme ödevi')).not.toBeInTheDocument()
  })
})
