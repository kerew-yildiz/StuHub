import { useEffect, useState } from 'react'

import { authFetch } from '../api/client'

type AuthedFileState = {
  /** İndirilen dosyanın `blob:` nesne URL'i — hazır olunca dolar. */
  blobUrl: string | null
  loading: boolean
  error: boolean
}

/** SaaS modda `Authorization: Bearer` gerektiren dosyaları (`<iframe src>` başlık
 * taşıyamaz) `authFetch` ile indirip `blob:` nesne URL'ine çevirir (Yetenek 06 §4 —
 * materyal/sunum önizlemesi). `path`, `authFetch` kuralına uygun `/api` ÖNEKSİZ verilir
 * (örn. `/materials/5/file`). Unmount/`path` değişiminde nesne URL'i serbest bırakılır. */
export function useAuthedFileUrl(path: string | null): AuthedFileState {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!path) {
      setBlobUrl(null)
      setLoading(false)
      setError(false)
      return
    }
    let cancelled = false
    let objectUrl: string | null = null
    setBlobUrl(null)
    setError(false)
    setLoading(true)
    authFetch(path)
      .then((response) => {
        if (!response.ok) throw new Error('dosya alınamadı')
        return response.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setBlobUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setError(true)
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
