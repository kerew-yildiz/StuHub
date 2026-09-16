import { useNavigate } from 'react-router-dom'

import { useShellStore } from '../stores/shellStore'
import { Maximize2, Minimize2, X } from 'lucide-react'

interface WorkspaceChromeProps {
  /** X'e basınca dönülecek hedef — bulunduğu feature'ın listesi/dashboard'ı (yönerge §27). */
  exitTo: string
  /** X'in aria-label'ı — nereye döneceğini açıkça söyler. */
  exitLabel?: string
}

/**
 * Workspace chrome — sağ üstte `[Fullscreen] [X]` (yönerge §26/§27).
 *
 * - Fullscreen: workspace fullscreen toggle. Shell'i (sidebar+header) gizler,
 *   workspace'i tüm uygulama alanına yayar. Browser fullscreen DEĞİLDİR — iki
 *   state ayrı değişkenlerde yaşar (shellStore.workspaceFullscreen vs
 *   browserFullscreen / Fullscreen API).
 * - X: global home'a DEĞİL, bulunduğu feature'ın listesine/dashboard'ına döner.
 */
export function WorkspaceChrome({ exitTo, exitLabel }: WorkspaceChromeProps) {
  const navigate = useNavigate()
  const workspaceFullscreen = useShellStore((s) => s.workspaceFullscreen)
  const toggleWorkspaceFullscreen = useShellStore((s) => s.toggleWorkspaceFullscreen)
  const setWorkspaceFullscreen = useShellStore((s) => s.setWorkspaceFullscreen)

  return (
    <div className="workspace-chrome" role="group" aria-label="Çalışma alanı kontrolleri">
      <button
        type="button"
        className="icon-btn"
        aria-label={workspaceFullscreen ? 'Çalışma alanı tam ekranından çık' : 'Çalışma alanını tam ekran yap'}
        title={workspaceFullscreen ? 'Tam ekrandan çık' : 'Tam ekran (shell gizlenir)'}
        onClick={() => {
          toggleWorkspaceFullscreen()
          if (!workspaceFullscreen) window.scrollTo({ top: 0 })
        }}
      >
        {workspaceFullscreen ? <Minimize2 size={18} aria-hidden="true" /> : <Maximize2 size={18} aria-hidden="true" />}
      </button>
      <button
        type="button"
        className="icon-btn"
        aria-label={exitLabel ?? 'Çalışma alanını kapat ve listeye dön'}
        title={exitLabel ?? 'Kapat'}
        onClick={() => {
          setWorkspaceFullscreen(false)
          navigate(exitTo)
        }}
      >
        <X size={18} aria-hidden="true" />
      </button>
    </div>
  )
}
