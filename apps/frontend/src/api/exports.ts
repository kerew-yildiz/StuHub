import { authFetch } from './client'

/** Dışa aktarma biçimi (flashcard setleri ve ders kartları için). */
export type FlashcardExportFormat = 'apkg' | 'csv' | 'md'

/** Yetkili indirme — `<a href>` gezinmesi `Authorization: Bearer` başlığını
 * taşımadığından SaaS modda 401 alınıyordu. İçerik `authFetch` ile çekilip blob
 * olarak indirilir; başarısızsa `false` döner ve hata mesajını çağrı yeri kendi
 * mevcut mekanizmasıyla gösterir. `path`, `authFetch` kuralına uygun olarak
 * `/api` öneki OLMADAN verilir. */
export async function downloadAuthed(path: string, filename: string): Promise<boolean> {
  try {
    const response = await authFetch(path)
    if (!response.ok) return false
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}
