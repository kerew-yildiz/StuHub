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

/** Not görüntüleyici — markdown + interaktif atıflar (Faz 3.3). */
export function NoteViewer({ note }: NoteViewerProps) {
  const [active, setActive] = useState<Citation | null>(null)
  const sections = splitSections(note)

  return (
    <div>
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
                  <h1 className="mt-0 mb-3 text-2xl font-semibold">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mt-6 mb-2 text-xl font-semibold">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mt-4 mb-2 text-lg font-semibold">{children}</h3>
                ),
                ul: ({ children }) => (
                  <ul className="mt-2 list-disc space-y-1 pl-6">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="mt-2 list-decimal space-y-1 pl-6">{children}</ol>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="mt-2 border-l-2 border-stuhub-border pl-3 text-stuhub-text-secondary">
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

      {active && <CitationPopup citation={active} onClose={() => setActive(null)} />}
    </div>
  )
}
