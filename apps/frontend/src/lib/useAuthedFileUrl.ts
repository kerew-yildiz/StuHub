import { useEffect, useState } from 'react'

import { ApiError, authFetch } from '../api/client'

type AuthedFileState = {
  /** İndirilen dosyanın `blob:` nesne URL'i — hazır olunca dolar. */
  blobUrl: string | null
  loading: boolean
  /** Kullanıcıya gösterilecek Türkçe hata mesajı; hata yoksa `null`. */
  error: string | null
}

/** Sunucuda dosya yok (404) — burada "tekrar deneyin" yanıltıcı olurdu. */
const NOT_FOUND_MESSAGE = 'Dosya sunucuda bulunamadı.'
const LOAD_FAILED_MESSAGE = 'Dosya yüklenemedi. Lütfen tekrar deneyin.'

/** SaaS modda `Authorization: Bearer` gerektiren dosyaları (`<iframe src>` başlık
 * taşıyamaz) `authFetch` ile indirip `blob:` nesne URL'ine çevirir (Yetenek 06 §4 —
 * materyal/sunum önizlemesi). `path`, `authFetch` kuralına uygun `/api` ÖNEKSİZ verilir
 * (örn. `/materials/5/file`). Unmount/`path` değişiminde nesne URL'i serbest bırakılır. */
export function useAuthedFileUrl(path: string | null): AuthedFileState {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!path) {
      setBlobUrl(null)
      setLoading(false)
      setError(null)
      return
    }
    let cancelled = false
    let objectUrl: string | null = null
    setBlobUrl(null)
    setError(null)
    setLoading(true)
    authFetch(path)
      .then((response) => {
        if (!response.ok) {
          throw new ApiError(
            response.status === 404 ? NOT_FOUND_MESSAGE : LOAD_FAILED_MESSAGE,
            response.status,
          )
        }
        return response.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setBlobUrl(objectUrl)
      })
      .catch((err: unknown) => {
        // Kullanıcıya yalnızca bilinçli üretilmiş Türkçe mesaj gösterilir; beklenmedik
        // hatalar (ayrıştırma vb.) ham metniyle sızdırılmaz.
        if (!cancelled) setError(err instanceof ApiError ? err.message : LOAD_FAILED_MESSAGE)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path])

  return { blobUrl, loading, error }
}
