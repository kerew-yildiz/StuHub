import { BASE_URL } from './client'

/** Dışa aktarma biçimi (flashcard setleri ve ders kartları için). */
export type FlashcardExportFormat = 'apkg' | 'csv' | 'md'

/**
 * Aynı kaynaktan dosya indirir. Backend `Content-Disposition: attachment`
 * döndürdüğünden sayfa değişmeden indirme başlar.
 */
export function downloadFile(url: string): void {
  const link = document.createElement('a')
  link.href = url
  document.body.appendChild(link)
  link.click()
  link.remove()
}

/** Notun Markdown dışa aktarma adresi. */
export function noteMarkdownUrl(noteId: number): string {
  return `${BASE_URL}/notes/${noteId}/export?format=md`
}

/** Flashcard seti dışa aktarma adresi (apkg / csv / md). */
export function flashcardSetExportUrl(setId: number, format: FlashcardExportFormat): string {
  return `${BASE_URL}/flashcard-sets/${setId}/export?format=${format}`
}

/** Dersin tüm kartlarını dışa aktarma adresi. */
export function courseFlashcardsExportUrl(
  courseId: number,
  format: FlashcardExportFormat,
): string {
  return `${BASE_URL}/courses/${courseId}/flashcards/export?format=${format}`
}

/** Dönem arşivi indirme adresi (zip). */
export function termArchiveUrl(termId: number, includeFiles: boolean): string {
  return `${BASE_URL}/terms/${termId}/archive?include_files=${includeFiles}`
}
