import ReactMarkdown from 'react-markdown'

import type { ConceptMapGuide, SummaryGuide } from '../api/guides'
import { conceptMapToMermaid } from '../lib/mermaid'
import { MermaidDiagram } from './MermaidDiagram'

interface GuideViewProps {
  guide: SummaryGuide | ConceptMapGuide
}

/** Özet rehberi — markdown + anahtar terim rozetleri + sınav odakları. */
function SummaryView({ guide }: { guide: SummaryGuide }) {
  const { summary_md, key_terms, exam_focus } = guide.content_json
  return (
    <div className="glass-panel p-5">
      <div className="text-sm leading-relaxed">
        <ReactMarkdown
          urlTransform={(url) => url}
          components={{
            p: ({ children }) => <p className="my-2">{children}</p>,
            ul: ({ children }) => <ul className="mt-1 list-disc space-y-1 pl-6">{children}</ul>,
            ol: ({ children }) => <ol className="mt-1 list-decimal space-y-1 pl-6">{children}</ol>,
            h2: ({ children }) => <h2 className="mt-4 text-lg font-semibold">{children}</h2>,
            h3: ({ children }) => <h3 className="mt-3 text-base font-semibold">{children}</h3>,
          }}
        >
          {summary_md}
        </ReactMarkdown>
      </div>

      {key_terms.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-stuhub-text-secondary">Anahtar Terimler</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {key_terms.map((term, index) => (
              <span
                key={`${term}-${index}`}
                className="glass-panel-subtle rounded-chip px-2 py-1 text-xs font-medium text-stuhub-accent"
              >
                {term}
              </span>
            ))}
          </div>
        </div>
      )}

      {exam_focus.length > 0 && (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-stuhub-text-secondary">Sınav Odakları</h3>
          <ul className="mt-2 list-disc space-y-1 pl-6 text-sm">
            {exam_focus.map((focus, index) => (
              <li key={`${focus}-${index}`}>{focus}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** Kavram haritası — Mermaid flowchart olarak render edilir (Whimsical entegrasyonu). */
function ConceptMapView({ guide }: { guide: ConceptMapGuide }) {
  const { nodes } = guide.content_json

  if (nodes.length === 0) {
    return (
      <div className="glass-panel p-5">
        <p className="text-sm text-stuhub-text-secondary">Kavram haritası boş.</p>
      </div>
    )
  }

  const definition = conceptMapToMermaid(guide.content_json)

  return (
    <div className="overflow-x-auto glass-panel p-5">
      <MermaidDiagram
        definition={definition}
        nodeMarkerAttr="data-cm-node"
        ariaLabel="Kavram haritası"
      />
    </div>
  )
}

/** Rehber görünümü — türe göre özet veya kavram haritası çizer (Faz V2.7). */
export function GuideView({ guide }: GuideViewProps) {
  if (guide.kind === 'summary') {
    return <SummaryView guide={guide} />
  }
  return <ConceptMapView guide={guide} />
}
