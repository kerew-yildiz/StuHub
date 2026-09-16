import { Component, type ErrorInfo, type ReactNode } from 'react'

import { RotateCcw } from 'lucide-react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Global React Error Boundary — render hatası beyaz ekran yerine toparlanabilir
 * bir fallback gösterir. App dışındaki her render hatası buraya düşer; event
 * handler / async hataları yakalamaz (onlar çağıran tarafın sorumluluğunda).
 *
 * Production'da stack gizlenir (bilgi sızdırmaz); hata konsola loglanır ki
 * diagnosis için iz bıraksın.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Observability: gerçek bir telemetry hattı bağlanana kadar yapılandırılmış log.
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  private handleRetry = (): void => {
    this.setState({ error: null })
  }

  private handleReload = (): void => {
    window.location.reload()
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="app-loading" role="alert">
        <div className="glass-panel max-w-md p-8 text-center">
          <h1 className="text-xl font-semibold">Bir şeyler ters gitti</h1>
          <p className="mt-3 text-sm leading-relaxed text-stuhub-text-secondary">
            Beklenmeyen bir hata oluştu. Tekrar deneyebilirsin — sorun sürerse sayfayı
            yenilemek genellikle çözer.
          </p>
          {import.meta.env.DEV && (
            <pre className="mt-4 max-h-40 overflow-y-auto rounded-control bg-stuhub-glass-2 p-3 text-left text-xs text-stuhub-text-secondary">
              {error.message}
              {'\n'}
              {error.stack}
            </pre>
          )}
          <div className="mt-6 flex items-center justify-center gap-3">
            <button type="button" className="btn-primary" onClick={this.handleRetry}>
              <RotateCcw size={15} aria-hidden="true" /> Tekrar dene
            </button>
            <button
              type="button"
              className="glass-panel-subtle glass-interactive rounded-control px-4 py-2 text-sm font-medium text-stuhub-text-secondary"
              onClick={this.handleReload}
            >
              Sayfayı yenile
            </button>
          </div>
        </div>
      </div>
    )
  }
}
