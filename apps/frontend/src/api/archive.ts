import { BASE_URL } from './client'

/** İçe aktarılan ders eşlemesi (eski id → yeni id). */
export interface ImportedCourse {
  old_id: number
  new_id: number
  name: string
}

/** Arşiv içe aktarma sonucu (backend ile birebir). */
export interface ArchiveImportResult {
  term_id: number
  term_name: string
  courses: ImportedCourse[]
  materials_imported: number
}

/** Arşiv zip'ini içe aktarır (POST /archive/import — multipart). */
export async function importArchive(
  file: File,
  includeFiles: boolean,
): Promise<ArchiveImportResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('include_files', includeFiles ? 'true' : 'false')

  const response = await fetch(`${BASE_URL}/archive/import`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    let detail = 'Arşiv içe aktarılamadı. Lütfen tekrar deneyin.'
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // gövde JSON değilse fallback mesajı kullan
    }
    throw new Error(detail)
  }
  return (await response.json()) as ArchiveImportResult
}
