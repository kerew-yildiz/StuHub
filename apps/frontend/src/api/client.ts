/** Backend API istemcisi (Faz 0.4 iskeleti — yol haritası 2.2). */

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const BASE_URL = '/api'

/** Tipik JSON API çağrısı; hata durumunda Türkçe mesajlı ApiError fırlatır. */
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData
  const response = await fetch(`${BASE_URL}${path}`, {
    // FormData için Content-Type otomatik belirlenir (multipart boundary)
    headers: isFormData
      ? (options?.headers ?? {})
      : {
          'Content-Type': 'application/json',
          ...(options?.headers ?? {}),
        },
    ...options,
  })
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
