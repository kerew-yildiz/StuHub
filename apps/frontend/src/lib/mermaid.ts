import type { ConceptEdge, ConceptMapContent, ConceptNode } from '../api/guides'

/** Mermaid düğüm/kenar etiketlerinde sorun çıkaran karakterleri kaçışlar. */
function escapeLabel(label: string): string {
  return label
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, ' ')
}

/** Mermaid kimlikleri harf/rakam/alt çizgi dışında karakter kabul etmez. */
function safeId(id: string): string {
  const cleaned = id.replace(/[^a-zA-Z0-9_]/g, '_')
  return /^[a-zA-Z_]/.test(cleaned) ? cleaned : `n_${cleaned}`
}

/** importance'a göre Mermaid `class` adı — çekirdek kavramlar farklı stillenir. */
function importanceClass(node: ConceptNode): string {
  if (node.importance >= 3) return 'cmCore'
  if (node.importance <= 1) return 'cmMinor'
  return 'cmNormal'
}

/**
 * Kavram haritası JSON'ını (nodes/edges) bir Mermaid `flowchart` tanımına çevirir.
 * DAG yapısı (birden fazla ebeveyn) desteklenir — Mermaid `mindmap` türü tekil
 * ebeveyne zorladığı için burada `flowchart` kullanılır.
 */
export function conceptMapToMermaid(content: ConceptMapContent): string {
  const { nodes, edges } = content
  const idMap = new Map<string, string>()
  nodes.forEach((node) => idMap.set(node.id, safeId(node.id)))

  const lines: string[] = ['flowchart LR']
  nodes.forEach((node) => {
    const id = idMap.get(node.id)!
    lines.push(`  ${id}["${escapeLabel(node.label)}"]:::${importanceClass(node)}`)
  })
  edges.forEach((edge: ConceptEdge) => {
    const from = idMap.get(edge.from)
    const to = idMap.get(edge.to)
    if (!from || !to) return
    if (edge.label && edge.label.trim()) {
      lines.push(`  ${from} -->|${escapeLabel(edge.label.trim())}| ${to}`)
    } else {
      lines.push(`  ${from} --> ${to}`)
    }
  })
  lines.push('  classDef cmCore stroke-width:2px')
  lines.push('  classDef cmNormal stroke-width:1px')
  lines.push('  classDef cmMinor stroke-width:1px,stroke-dasharray: 3 2')
  return lines.join('\n')
}
