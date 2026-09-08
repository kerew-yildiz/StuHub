import { useEffect, useRef, useState } from 'react'

interface MermaidDiagramProps {
  /** Mermaid tanım metni (ör. `flowchart LR ...`). */
  definition: string
  /** Render edilen SVG içindeki her düğüme eklenir (test/erişilebilirlik amaçlı). */
  nodeMarkerAttr?: string
  /** SVG'nin erişilebilirlik etiketi. */
  ariaLabel?: string
}

let mermaidInitDone = false

async function ensureMermaidInitialized() {
  const mermaid = (await import('mermaid')).default
  if (!mermaidInitDone) {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      fontFamily: 'inherit',
      theme: 'base',
      // NOT: mermaid'in dahili renk motoru (khroma) `var(--...)` ayrıştıramıyor —
      // tema tokenlarının (theme.css) düz karşılıkları kullanılmalı (tek koyu tema var).
      themeVariables: {
        background: '#1c1c1e',
        primaryColor: '#2b2b2e',
        primaryTextColor: '#fafafa',
        primaryBorderColor: 'rgba(255, 255, 255, 0.24)',
        lineColor: '#ffffff',
        secondaryColor: '#2b2b2e',
        tertiaryColor: '#2b2b2e',
        edgeLabelBackground: '#1c1c1e',
        fontSize: '13px',
      },
      flowchart: { htmlLabels: true, curve: 'basis' },
    })
    mermaidInitDone = true
  }
  return mermaid
}

/** Bir Mermaid tanımını (flowchart/mindmap/…) SVG'ye render eden genel bileşen. */
export function MermaidDiagram({ definition, nodeMarkerAttr, ariaLabel }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  // Her render için benzersiz kimlik — aynı sayfada birden fazla diyagram çakışmasın.
  const renderIdRef = useRef(`mmd-${Math.random().toString(36).slice(2)}`)

  useEffect(() => {
    let cancelled = false
    setError(null)
    void (async () => {
      try {
        const mermaid = await ensureMermaidInitialized()
        const { svg } = await mermaid.render(renderIdRef.current, definition)
        if (cancelled || !containerRef.current) return
        containerRef.current.innerHTML = svg
        if (ariaLabel) {
          containerRef.current.querySelector('svg')?.setAttribute('aria-label', ariaLabel)
        }
        if (nodeMarkerAttr) {
          containerRef.current.querySelectorAll('.node').forEach((el) => {
            el.setAttribute(nodeMarkerAttr, '')
          })
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Diyagram render edilemedi.')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [definition, nodeMarkerAttr, ariaLabel])

  if (error) {
    return <p className="text-sm text-stuhub-error">Diyagram render edilemedi: {error}</p>
  }

  return <div ref={containerRef} className="mermaid-diagram overflow-x-auto" />
}
