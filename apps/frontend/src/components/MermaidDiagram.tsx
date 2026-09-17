import { useEffect, useRef, useState } from 'react'

interface MermaidDiagramProps {
  /** Mermaid tanım metni (ör. `flowchart LR ...`). */
  definition: string
  /** Render edilen SVG içindeki her düğüme eklenir (test/erişilebilirlik amaçlı). */
  nodeMarkerAttr?: string
  /** SVG'nin erişilebilirlik etiketi. */
  ariaLabel?: string
}

let sonTema: string | null = null

/** Mermaid motoru CSS degiskeni okuyamaz (khroma `var(...)` ayristirmaz) — guncel
 * kutbun COZULMUS token degerleri okunur. Diyagram tek renk setiyle cizildigi
 * icin tema degisiminde yeniden init edilir (bkz. bilesen ici gozlemci). */
function temaDegiskenleri(): Record<string, string> {
  const stil = getComputedStyle(document.documentElement)
  const oku = (ad: string, varsayilan: string) => stil.getPropertyValue(ad).trim() || varsayilan
  const zemin = oku('--stuhub-bg', '#000')
  const dugum = oku('--stuhub-diagram-node', '#2b2b2e')
  return {
    background: zemin,
    primaryColor: dugum,
    primaryTextColor: oku('--stuhub-text', '#fafafa'),
    primaryBorderColor: oku('--stuhub-diagram-border', 'rgba(255,255,255,.24)'),
    lineColor: oku('--stuhub-diagram-line', '#ffffff'),
    secondaryColor: dugum,
    tertiaryColor: dugum,
    edgeLabelBackground: zemin,
    fontSize: '13px',
  }
}

async function ensureMermaidInitialized() {
  // Dinamik import bilincli: mermaid ~1MB'lik ayri paket, kavram haritasi
  // goruntulenene kadar ana pakete girmemeli. (Statik import mumkun ama
  // rota agirligini gereksiz buyutur.)
  const mermaid = (await import('mermaid')).default
  const tema = document.documentElement.dataset.theme ?? 'dark'
  if (sonTema !== tema) {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      fontFamily: 'inherit',
      theme: 'base',
      themeVariables: temaDegiskenleri(),
      flowchart: { htmlLabels: true, curve: 'basis' },
    })
    sonTema = tema
  }
  return mermaid
}

/** Bir Mermaid tanımını (flowchart/mindmap/…) SVG'ye render eden genel bileşen. */
export function MermaidDiagram({ definition, nodeMarkerAttr, ariaLabel }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  // Tema degisimi (html[data-theme]) SVG'nin renk setini degistirir → diyagram
  // yeniden cizilir. Sunucudan gelen ayar (applyTheme) da bu yolu tetikler.
  const [tema, setTema] = useState(() => document.documentElement.dataset.theme ?? 'dark')
  // Her render için benzersiz kimlik — aynı sayfada birden fazla diyagram çakışmasın.
  const renderIdRef = useRef(`mmd-${Math.random().toString(36).slice(2)}`)

  useEffect(() => {
    const gozlemci = new MutationObserver(() =>
      setTema(document.documentElement.dataset.theme ?? 'dark'),
    )
    gozlemci.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => gozlemci.disconnect()
  }, [])

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
  }, [definition, nodeMarkerAttr, ariaLabel, tema])

  if (error) {
    return <p className="text-sm text-stuhub-error">Diyagram render edilemedi: {error}</p>
  }

  return <div ref={containerRef} className="mermaid-diagram overflow-x-auto" />
}
