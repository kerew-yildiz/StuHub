import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

import type { SavedNote } from '../api/notes'
import { normalizeNoteMarkdown } from '../lib/noteCleanup'

interface NoteViewerProps {
  note: SavedNote
}

interface RenderedSection {
  heading: string | null
  body: string
}

/** content_md'yi başlık bazlı bölerek bölümlere ayırır.
 *
 * ATIF SİSTEMİ KALDIRILDI (2026-09-19): atıf çipleri, atıf pop-up'ı ve Kaynakça
 * bölümü kullanıcıya GÖSTERİLMEZ. Gövdede kalıntı `[n]`/`⟨n⟩` işaretleri ve
 * eski kayıtlardan gelen `## Kaynakça` bölümü burada da temizlenir.
 *
 * `normalizeNoteMarkdown` SON SAVUNMA HATTI: kayıtlı içerik modelin JSON zarfını
 * taşıyorsa (bkz. `lib/noteCleanup`) burada açılır — ekranda ham JSON/kod çiti görünmez. */
function splitSections(note: SavedNote): RenderedSection[] {
  const contentMd = stripBibliography(normalizeNoteMarkdown(note.content_md))
  const sections: RenderedSection[] = []
  const lines = contentMd.split('\n')
  let current: RenderedSection | null = null

  for (const line of lines) {
    const match = line.match(/^(#{1,4})\s+(.+?)\s*$/)
    if (match) {
      if (current) sections.push(current)
      current = { heading: match[2], body: '' }
    } else if (current) {
      current.body += `${line}\n`
    }
  }
  if (current) sections.push(current)

  if (sections.length === 0) {
    sections.push({ heading: null, body: contentMd })
  }
  return sections
}

/** Eski kayıtlardan kalabilecek `## Kaynakça` bölümünü (ve altındaki her şeyi) siler. */
function stripBibliography(contentMd: string): string {
  const index = contentMd.search(/^##\s+Kaynakça\s*$/m)
  return index === -1 ? contentMd : contentMd.slice(0, index).trimEnd()
}

/** Kalıntı atıf numaralarını temizler (atıf sistemi kaldırıldı; kullanıcıya gösterilmez). */
function cleanCitationMarkers(body: string): string {
  return body
    .replace(/⟨\d+⟩/g, '')
    .replace(/\[\d+\]/g, '')
    .replace(/ {2,}/g, ' ')
    .replace(/ ([,.!?;:])/g, '$1')
}

/** Not görüntüleyici — markdown + daralt/genişlet (tam not / liste görünümü; kullanıcı
 * isteği). Daralt modunda yalnızca bölüm başlıkları listelenir; başlığa tıklayınca o
 * bölüm açılır. */
export function NoteViewer({ note }: NoteViewerProps) {
  const [outlineMode, setOutlineMode] = useState(false)
  const sections = splitSections(note)

  return (
    <div className="glass-panel px-5 py-7 sm:px-8 sm:py-9">
      <div className="mx-auto max-w-[92ch]">
        {/* Daralt/genişlet — yalnızca birden fazla bölüm varken anlamlı. */}
        {sections.length > 1 && (
          <div className="mb-6 flex justify-end">
            <button
              type="button"
              onClick={() => setOutlineMode((v) => !v)}
              aria-pressed={outlineMode}
              className="glass-panel-subtle glass-interactive rounded-control px-3 py-1.5 text-xs font-medium text-stuhub-text-secondary"
            >
              {outlineMode ? 'Tam not' : 'Daralt (liste görünümü)'}
            </button>
          </div>
        )}
        {outlineMode ? (
          <nav className="space-y-1" aria-label="Not bölümleri">
            {sections.map((section, index) => (
              <button
                key={`${section.heading ?? 'intro'}-${index}`}
                type="button"
                onClick={() => {
                  setOutlineMode(false)
                  // Bölüme yumuşak kaydır — genişletilmiş görünümde hedef bölüm.
                  requestAnimationFrame(() => {
                    document.getElementById(`note-section-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  })
                }}
                className="flex w-full items-center justify-between gap-3 rounded-control px-3 py-2.5 text-left transition-colors duration-[var(--duration-micro)] hover:bg-stuhub-glass-2-hover"
              >
                <span className="min-w-0 truncate text-sm font-medium text-stuhub-text">{section.heading ?? 'Giriş'}</span>
                <span className="shrink-0 text-xs text-stuhub-text-muted">{section.body.trim().split(/\s+/).length} kelime</span>
              </button>
            ))}
          </nav>
        ) : (
        <div className="space-y-10">
        {sections.map((section, index) => (
          <section
            key={`${section.heading ?? 'intro'}-${index}`}
            id={`note-section-${index}`}
            /* Gövde metni tam beyazın biraz altında: başlık/kalın vurgu ile düz metin
               arasında ayrım kalsın, ama okunabilirlik düşmesin. */
            className="text-[15.5px] leading-[1.75] text-stuhub-text/80"
          >
            <ReactMarkdown
              /* URL allow-list: http(s)/mailto/tel/relative/anchor. Atıf şeması artık
               * yok (atıf sistemi kaldırıldı); javascript:/data: URI'ları engellenir. */
              urlTransform={(url) =>
                /^(https?:|mailto:|tel:|[./#])/i.test(url) ? url : ''
              }
              components={{
                /* Hiyerarşi yalnızca boşluk + punto + ağırlıkla kuruluyor; renkli/çizgili
                   vurgu yok (sol-kenar çizgisi 2026-09-08'de kaldırıldı — en tanınabilir
                   "AI-üretimi arayüz" izlerinden biriydi). */
                /* Başlıklar: uzun kesintisiz dizeler (ör. tekrarlanan harfler) satırı
                 * taşırıp yatay kaydırmaya ve üst üste binmeye yol açıyordu —
                 * overflow-wrap:anywhere ile kelime içi kırılma son çare olarak devreye girer. */
                h1: ({ children }) => (
                  <h1 className="mt-0 mb-4 text-[26px] font-semibold leading-tight tracking-tight text-stuhub-text [overflow-wrap:anywhere]">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-8 mb-3 text-[21px] font-semibold leading-snug tracking-tight text-stuhub-text [overflow-wrap:anywhere]">
                    {children}
                  </h2>
                ),
                /* Bölüm başlığı: `splitSections` her bölümü `### başlık` olarak veriyor,
                   yani h3 pratikte notun ana başlığı — ikincil renk okunaksız kalıyordu. */
                h3: ({ children }) => (
                  <h3 className="mt-0 mb-4 text-[19px] font-semibold leading-snug tracking-tight text-stuhub-text [overflow-wrap:anywhere]">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="mt-6 mb-2 text-[16px] font-semibold text-stuhub-text [overflow-wrap:anywhere]">
                    {children}
                  </h4>
                ),
                p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-stuhub-text">{children}</strong>
                ),
                ul: ({ children }) => (
                  <ul className="mb-4 list-disc space-y-2 pl-5 marker:text-stuhub-text-secondary last:mb-0">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="mb-4 list-decimal space-y-2 pl-5 marker:text-stuhub-text-secondary last:mb-0">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="pl-1 [&>ul]:mt-2 [&>ol]:mt-2">{children}</li>,
                code: ({ children }) => (
                  <code className="rounded-sm bg-stuhub-glass-1-hover px-1.5 py-0.5 font-mono text-[13.5px]">
                    {children}
                  </code>
                ),
                hr: () => <hr className="my-8 border-stuhub-border" />,
                blockquote: ({ children }) => (
                  <blockquote className="mb-4 rounded-sm border-l-2 bg-stuhub-callout-bg px-4 py-3 text-[15px] text-stuhub-text-secondary last:mb-0"
                    style={{ borderLeftColor: 'var(--stuhub-callout-border)' }}
                  >
                    {children}
                  </blockquote>
                ),
              }}
            >
              {section.heading
                ? `### ${section.heading}\n\n${cleanCitationMarkers(section.body)}`
                : cleanCitationMarkers(section.body)}
            </ReactMarkdown>
          </section>
        ))}
        </div>
        )}
      </div>
    </div>
  )
}
