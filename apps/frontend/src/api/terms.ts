import { apiFetch } from './client'

/** Dönem (backend TermOut ile birebir). */
export interface Term {
  id: number
  name: string
  start_date: string | null
  end_date: string | null
  created_at: string
}

export interface TermInput {
  name: string
  start_date?: string | null
  end_date?: string | null
}

export const termsApi = {
  list: () => apiFetch<Term[]>('/terms'),
  create: (input: TermInput) =>
    apiFetch<Term>('/terms', { method: 'POST', body: JSON.stringify(input) }),
  update: (id: number, input: TermInput) =>
    apiFetch<Term>(`/terms/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  remove: (id: number) => apiFetch<void>(`/terms/${id}`, { method: 'DELETE' }),
}
