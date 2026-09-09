import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

import type { Citation, SavedNote } from '../api/notes'
import { CitationPopup } from './CitationPopup'

interface NoteViewerProps {
  note: SavedNote
}

interface RenderedSection {
  heading: string | null
  body: string
  citations: Citation[]
}

const CITATION_SCHEME = 'stuhub-citation://'

/** Web kaynaklı atıf mı? (source_type "web" ya da url varsa) — API'ye fetch yapılmaz. */
function isWebCitation(citation: Citation): boolean {
  return citation.source_type === 'web' || Boolean(citation.url)
}

/** Başlık ↔ konu adı esnek eşleşmesi (LLM başlıkları konu adından sapabilir). */
function topicMatches(heading: string, topic: string): boolean {
  const normalize = (s: string) => s.toLowerCase().replace(/[^\w\s]/g, '').trim()
  const a = normalize(heading)
  const b = normalize(topic)
  if (!a || !b) return false
  if (a === b) return true
  if (b.length >= 4 && a.includes(b)) return true
  return a.length >= 4 && b.includes(a)
}

/** content_md'yi başlık bazlı bölerek her bölüme kendi atıf haritasını bağlar. */
function splitSections(note: SavedNote): RenderedSection[] {
  const topicMap = new Map<string, Citation[]>()
  for (const topic of note.citations_json.topics ?? []) {
    topicMap.set(topic.topic, topic.citations)
  }

  const sections: RenderedSection[] = []
  const lines = note.content_md.split('\n')
  let current: RenderedSection | null = null

  for (const line of lines) {
    const match = line.match(/^(#{1,4})\s+(.+?)\s*$/)
    if (match) {
      if (current) sections.push(current)
      const heading = match[2]
      let citations: Citation[] = []
      for (const [topicName, topicCitations] of topicMap) {
        if (topicMatches(heading, topicName)) {
          citations = topicCitations
          break
        }
      }
      current = { heading, body: '', citations }
    } else if (current) {
      current.body += `${line}\n`
    }
  }
  if (current) sections.push(current)

  if (sections.length === 0) {
    sections.push({ heading: null, body: note.content_md, citations: [] })
  }
  return sections
}

/** Atıf numaralarını markdown bağlantısına çevirir: [1] → [1](stuhub-citation://1) */
function enhanceMarkdown(body: string): string {
  return body.replace(/\[(\d+)\]/g, `[$1](${CITATION_SCHEME}$1)`)
}

function CitationLink({
  href,
  children,
  citations,
  onOpenCitation,
}: {
  href?: string
  children?: React.ReactNode
  citations: Citation[]
  onOpenCitation: (citation: Citation) => void
}) {
  if (href?.startsWith(CITATION_SCHEME)) {
    const id = Number(href.slice(CITATION_SCHEME.length))
    const citation = citations.find((c) => c.id === id)
    if (citation) {
      return (
        <button
          type="button"
          onClick={() => onOpenCitation(citation)}
          className="mx-0.5 inline-block rounded-sm bg-stuhub-accent/15 px-1 text-sm font-semibold text-stuhub-accent transition-colors duration-150 hover:bg-stuhub-accent/25"
          title="Atıf kaynağını göster"
        >
          [{id}]
        </button>
      )
    }
  }
  return <span>{children}</span>
}

/** Not görüntüleyici — markdown + interaktif atıflar. */
export function NoteViewer({ note }: NoteViewerProps) {
  const [active, setActive] = useState<Citation | null>(null)
  const sections = splitSections(note)

  return (
    <div className="glass-panel px-5 py-7 sm:px-8 sm:py-9">
      <div className="mx-auto max-w-[92ch] space-y-10">
        {sections.map((section, index) => (
          <section
            key={`${section.heading ?? 'intro'}-${index}`}
            /* Gövde metni tam beyazın biraz altında: başlık/kalın vurgu ile düz metin
               arasında ayrım kalsın, ama okunabilirlik düşmesin. */
            className="text-[15.5px] leading-[1.75] text-stuhub-text/80"
          >
            <ReactMarkdown
              urlTransform={(url) => url}
              components={{
                a: ({ href, children }) => (
                  <CitationLink
                    href={href}
                    children={children}
                    citations={section.citations}
                    onOpenCitation={setActive}
                  />
                ),
                /* Hiyerarşi yalnızca boşluk + punto + ağırlıkla kuruluyor; renkli/çizgili
                   vurgu yok (sol-kenar çizgisi 2026-09-08'de kaldırıldı — en tanınabilir
                   "AI-üretimi arayüz" izlerinden biriydi). */
                h1: ({ children }) => (
                  <h1 className="mt-0 mb-4 text-[26px] font-semibold leading-tight tracking-tight text-stuhub-text">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-8 mb-3 text-[21px] font-semibold leading-snug tracking-tight text-stuhub-text">
                    {children}
                  </h2>
                ),
                /* Bölüm başlığı: `splitSections` her bölümü `### başlık` olarak veriyor,
                   yani h3 pratikte notun ana başlığı — ikincil renk okunaksız kalıyordu. */
                h3: ({ children }) => (
                  <h3 className="mt-0 mb-4 text-[19px] font-semibold leading-snug tracking-tight text-stuhub-text">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="mt-6 mb-2 text-[16px] font-semibold text-stuhub-text">
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
              {section.heading ? `### ${section.heading}\n\n${enhanceMarkdown(section.body)}` : enhanceMarkdown(section.body)}
            </ReactMarkdown>
          </section>
        ))}
      </div>

      {active && (
        <CitationPopup
          citation={active}
          preloadedText={isWebCitation(active) ? (active.quote ?? undefined) : undefined}
          sourceLabel={isWebCitation(active) ? (active.title ?? active.url ?? undefined) : undefined}
          onClose={() => setActive(null)}
        />
      )}
    </div>
  )
}
