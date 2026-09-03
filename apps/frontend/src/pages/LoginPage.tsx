import { useState } from 'react'

import { supabaseClient } from '../lib/supabaseClient'

type Mode = 'signin' | 'signup'

/** SaaS modda oturum yokken gösterilen giriş ekranı — tüm yönlendirilmiş rotaların yerine geçer. */
export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<Mode>('signin')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!supabaseClient) {
      setError('Kimlik doğrulama şu anda kullanılamıyor.')
      return
    }
    setLoading(true)
    setError('')
    setInfo('')

    const { error: authError } =
      mode === 'signin'
        ? await supabaseClient.auth.signInWithPassword({ email, password })
        : await supabaseClient.auth.signUp({ email, password })

    setLoading(false)

    if (authError) {
      setError(
        mode === 'signin'
          ? 'Giriş başarısız oldu. E-posta veya şifre hatalı.'
          : 'Hesap oluşturulamadı. Bilgileri kontrol edip tekrar deneyin.',
      )
      return
    }

    if (mode === 'signup') {
      setInfo('Hesabın oluşturuldu. E-postana gelen bağlantıyla doğrulama yapman gerekebilir.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stuhub-bg px-6 text-stuhub-text">
      <div className="w-full max-w-sm rounded-md border border-stuhub-border bg-stuhub-surface p-6">
        <h1 className="text-2xl font-semibold tracking-tight">StuHub</h1>
        <p className="mt-2 text-sm text-stuhub-text-secondary">
          Devam etmek için giriş yap veya hesap oluştur.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium">
              E-posta
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium">
              Şifre
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border border-stuhub-border bg-stuhub-bg px-3 py-2 text-sm outline-none transition-colors duration-150 focus:border-stuhub-accent"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-sm bg-stuhub-error/10 px-4 py-2 text-sm text-stuhub-error">
              {error}
            </p>
          )}
          {info && (
            <p role="status" className="rounded-sm bg-stuhub-success/10 px-4 py-2 text-sm text-stuhub-success">
              {info}
            </p>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading}
              onClick={() => setMode('signin')}
              className="flex-1 rounded-sm bg-stuhub-accent px-4 py-2 text-sm font-medium text-stuhub-on-accent transition-colors duration-150 hover:bg-stuhub-accent-hover disabled:opacity-60"
            >
              {loading && mode === 'signin' ? 'Giriş yapılıyor…' : 'Giriş yap'}
            </button>
            <button
              type="submit"
              disabled={loading}
              onClick={() => setMode('signup')}
              className="flex-1 rounded-sm border border-stuhub-border px-4 py-2 text-sm font-medium transition-colors duration-150 hover:border-stuhub-border-strong disabled:opacity-60"
            >
              {loading && mode === 'signup' ? 'Hesap oluşturuluyor…' : 'Hesap oluştur'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
