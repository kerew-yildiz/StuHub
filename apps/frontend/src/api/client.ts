/** Backend API istemcisi (Faz 0.4 iskeleti — yol haritası 2.2). */

import { supabaseClient } from '../lib/supabaseClient'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const BASE_URL = '/api'

/** SaaS modda authStore tarafından güncellenen geçerli Supabase access token'ı.
 * Döngüsel import'tan kaçınmak için modül seviyesinde tutulur; yerel modda hep null kalır. */
let currentAccessToken: string | null = null

export function setAccessToken(token: string | null): void {
  currentAccessToken = token
}

/** Kimlik doğrulamalı `fetch` — her API dosyasının ortak temeli.
 *
 * SaaS modda proaktif token yenilemesi (Supabase'in arka plan zamanlayıcısı) arka
 * planda/askıya alınmış sekmelerde gecikebilir/kaçabilir — 401 alınırsa burada
 * REAKTİF olarak `refreshSession()` denenir ve istek bir kez tekrarlanır; bu ikinci
 * deneme de 401 dönerse (gerçekten oturum kapalıysa) 401 olduğu gibi döner.
 *
 * Ham `Response` döner (JSON'a çevirmez) — SSE akışı okuyan çağrı yerleri
 * (`notes.ts`/`quizzes.ts`/`flashcards.ts`/`overall.ts` üretim akışları) `response.body`
 * gerektirir; `apiFetch` bunun üstüne JSON ayrıştırma katmanı ekler.
 */
export async function authFetch(path: string, options?: RequestInit): Promise<Response> {
  const isFormData = options?.body instanceof FormData
  const doFetch = () =>
    fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        // FormData için Content-Type otomatik belirlenir (multipart boundary)
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(currentAccessToken ? { Authorization: `Bearer ${currentAccessToken}` } : {}),
        ...(options?.headers ?? {}),
      },
    })

  let response = await doFetch()
  if (response.status === 401 && supabaseClient) {
    const { data, error } = await supabaseClient.auth.refreshSession()
    if (!error && data.session) {
      setAccessToken(data.session.access_token)
      response = await doFetch()
    }
  }
  return response
}

/** Tipik JSON API çağrısı; hata durumunda Türkçe mesajlı ApiError fırlatır. */
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await authFetch(path, options)
  if (!response.ok) {
    throw new ApiError('Sunucu isteği başarısız oldu. Lütfen tekrar deneyin.', response.status)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

/** Sağlık kontrolü — backend ayakta mı? (GET /health) */
export async function getHealth(): Promise<boolean> {
  try {
    const response = await fetch('/health')
    if (!response.ok) return false
    const body = (await response.json()) as { status?: string }
    return body.status === 'ok'
  } catch {
    return false
  }
}

export interface HealthInfo {
  status: string
  app: string
  version: string
  saas_mode: boolean
}

/** Sağlık + mod bilgisi — SaaS geçidi için (GET /health) */
export async function getHealthInfo(): Promise<HealthInfo> {
  const response = await fetch('/health')
  if (!response.ok) {
    throw new ApiError('Sağlık kontrolü başarısız oldu.', response.status)
  }
  return (await response.json()) as HealthInfo
}
