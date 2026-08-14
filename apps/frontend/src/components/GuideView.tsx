import ReactMarkdown from 'react-markdown'

import type {
  ConceptEdge,
  ConceptMapGuide,
  ConceptNode,
  SummaryGuide,
} from '../api/guides'

interface GuideViewProps {
  guide: SummaryGuide | ConceptMapGuide
}

/** Özet rehberi — markdown + anahtar terim rozetleri + sınav odakları. */
function SummaryView({ guide }: { guide: SummaryGuide }) {
  const { summary_md, key_terms, exam_focus } = guide.content_json
  return (
    <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-5">
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
                className="rounded-sm bg-stuhub-accent/10 px-2 py-1 text-xs font-medium text-stuhub-accent"
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

const NODE_W = 150
const NODE_H = 44
const LAYER_GAP = 200
const NODE_GAP = 20
const MARGIN = 24

interface Position {
  x: number
  y: number
}

/** Bağımlılıksız katmanlı düzen: in-degree 0 kökler → BFS ile katmanlar. */
function layoutMap(
  nodes: ConceptNode[],
  edges: ConceptEdge[],
): { positions: Map<string, Position>; width: number; height: number; roots: string[] } {
  const adjacency = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  nodes.forEach((node) => {
    adjacency.set(node.id, [])
    inDegree.set(node.id, 0)
  })
  edges.forEach((edge) => {
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, [])
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, [])
    if (!inDegree.has(edge.from)) inDegree.set(edge.from, 0)
    if (!inDegree.has(edge.to)) inDegree.set(edge.to, 0)
    adjacency.get(edge.from)!.push(edge.to)
    inDegree.set(edge.to, (inDegree.get(edge.to) ?? 0) + 1)
  })

  // Kökler: gelen kenarı olmayan düğümler; yoksa en yüksek importance.
  let roots = nodes.filter((node) => inDegree.get(node.id) === 0).map((node) => node.id)
  if (roots.length === 0 && nodes.length > 0) {
    roots = [[...nodes].sort((a, b) => b.importance - a.importance)[0].id]
  }

  const layer = new Map<string, number>()
  roots.forEach((root) => layer.set(root, 0))
  const queue = [...roots]
  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLayer = layer.get(current)!
    for (const next of adjacency.get(current) ?? []) {
      if (!layer.has(next)) {
        layer.set(next, currentLayer + 1)
        queue.push(next)
      }
    }
  }

  // Döngü/takım yüzünden erişilemeyenler tek bir katmana düşer.
  let maxLayer = 0
  layer.forEach((value) => {
    if (value > maxLayer) maxLayer = value
  })
  const fallbackLayer = maxLayer + 1
  nodes.forEach((node) => {
    if (!layer.has(node.id)) layer.set(node.id, fallbackLayer)
  })

  const byLayer = new Map<number, ConceptNode[]>()
  nodes.forEach((node) => {
    const level = layer.get(node.id)!
    const list = byLayer.get(level) ?? []
    list.push(node)
    byLayer.set(level, list)
  })
  byLayer.forEach((list) => list.sort((a, b) => b.importance - a.importance))

  const layerNumbers = [...byLayer.keys()].sort((a, b) => a - b)
  const positions = new Map<string, Position>()
  layerNumbers.forEach((level, levelIndex) => {
    const list = byLayer.get(level)!
    let y = MARGIN
    list.forEach((node) => {
      positions.set(node.id, { x: MARGIN + levelIndex * LAYER_GAP, y })
      y += NODE_H + NODE_GAP
    })
  })

  const maxRows = Math.max(...layerNumbers.map((level) => byLayer.get(level)!.length))
  const height = maxRows * NODE_H + (maxRows - 1) * NODE_GAP + MARGIN * 2
  const width = MARGIN * 2 + (layerNumbers.length - 1) * LAYER_GAP + NODE_W

  return { positions, width, height, roots }
}

/** Kavram haritası — SVG çizim (ok kenarları, importance'a göre kök düğümler). */
function ConceptMapView({ guide }: { guide: ConceptMapGuide }) {
  const { nodes, edges } = guide.content_json

  if (nodes.length === 0) {
    return (
      <div className="rounded-md border border-stuhub-border bg-stuhub-surface p-5">
        <p className="text-sm text-stuhub-text-secondary">Kavram haritası boş.</p>
      </div>
    )
  }

  const { positions, width, height, roots } = layoutMap(nodes, edges)
  const markerId = `cm-arrow-${guide.id}`

  return (
    <div className="overflow-x-auto rounded-md border border-stuhub-border bg-stuhub-surface p-5">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ minWidth: 420 }}
        role="img"
        aria-label="Kavram haritası"
      >
        <defs>
          <marker
            id={markerId}
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M0,0 L0,8 L8,4 z" style={{ fill: 'var(--stuhub-accent)' }} />
          </marker>
        </defs>

        {edges.map((edge, index) => {
          const from = positions.get(edge.from)
          const to = positions.get(edge.to)
          if (!from || !to) return null
          const x1 = from.x + NODE_W
          const y1 = from.y + NODE_H / 2
          const x2 = to.x
          const y2 = to.y + NODE_H / 2
          const midX = (x1 + x2) / 2
          const midY = (y1 + y2) / 2
          return (
            <g key={`${edge.from}-${edge.to}-${index}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2 - 4}
                y2={y2}
                style={{ stroke: 'var(--stuhub-accent)', strokeWidth: 1.5 }}
                markerEnd={`url(#${markerId})`}
              />
              {edge.label && (
                <text
                  x={midX}
                  y={midY - 6}
                  textAnchor="middle"
                  fontSize={11}
                  style={{ fill: 'var(--stuhub-text-secondary)' }}
                >
                  {edge.label}
                </text>
              )}
            </g>
          )
        })}

        {nodes.map((node) => {
          const position = positions.get(node.id)!
          const isRoot = roots.includes(node.id)
          return (
            <g key={node.id} data-cm-node>
              <rect
                x={position.x}
                y={position.y}
                width={NODE_W}
                height={NODE_H}
                rx={6}
                style={{
                  fill: 'var(--stuhub-surface)',
                  stroke: isRoot ? 'var(--stuhub-accent)' : 'var(--stuhub-border)',
                  strokeWidth: isRoot ? 2 : 1,
                }}
              />
              <text
                x={position.x + NODE_W / 2}
                y={position.y + NODE_H / 2}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={13}
                fontWeight={500}
                style={{ fill: 'var(--stuhub-text)' }}
              >
                {node.label}
              </text>
            </g>
          )
        })}
      </svg>
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
