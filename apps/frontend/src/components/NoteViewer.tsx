import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

import type { Citation, SavedNote } from '../api/notes'
import { hueColorVar, hueSoftVar } from '../lib/courseColors'
import { CitationPopup } from './CitationPopup'

interface NoteViewerProps {
  note: SavedNote
  /** Ders hue id'si — bölüm başlıkları bu renkle şeritlenir (Şema 5). */
  hueId?: string
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

/** Not görüntüleyici — markdown + interaktif atıflar + ders renk şeritleri (Şema 5). */
export function NoteViewer({ note, hueId }: NoteViewerProps) {
  const [active, setActive] = useState<Citation | null>(null)
  const sections = splitSections(note)

  return (
    <div className="glass-panel p-6">
      <div className="space-y-6">
        {sections.map((section, index) => (
          <section
            key={`${section.heading ?? 'intro'}-${index}`}
            className="max-w-[68ch] text-base leading-relaxed"
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
                h1: ({ children }) => (
                  <h1 className="mt-0 mb-3 border-l-4 pl-3 text-2xl font-semibold"
                    style={
                      hueId
                        ? { borderLeftColor: hueColorVar(hueId), backgroundColor: hueSoftVar(hueId) }
                        : undefined
                    }
                  >
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-6 mb-2 border-l-4 pl-3 text-xl font-semibold"
                    style={hueId ? { borderLeftColor: hueColorVar(hueId) } : undefined}
                  >
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mt-4 mb-2 border-l-4 pl-3 text-lg font-semibold"
                    style={hueId ? { borderLeftColor: hueColorVar(hueId) } : undefined}
                  >
                    {children}
                  </h3>
                ),
                ul: ({ children }) => (
                  <ul className="mt-2 list-disc space-y-1 pl-6">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="mt-2 list-decimal space-y-1 pl-6">{children}</ol>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="mt-3 rounded-sm border-l-4 bg-stuhub-callout-bg px-4 py-2 text-[15px] text-stuhub-text"
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
