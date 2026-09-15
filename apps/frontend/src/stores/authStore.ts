import type { Session, User } from '@supabase/supabase-js'
import { create } from 'zustand'

import { getHealthInfo, setAccessToken } from '../api/client'
import { supabaseClient } from '../lib/supabaseClient'

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
  saasMode: boolean
  /** Açılış kontrolü zaman aşımına uğradı/başarısız oldu — kullanıcıya tekrar dene ekranı. */
  failed: boolean
  init: () => Promise<void>
}

// Açılışta iki ağ çağrısı bekleniyor (`/health` + Supabase `getSession`). Bunlar
// timeout'suz `await` edildiğinde backend yanıt vermezse hiçbiri reject etmiyor,
// `loading` sonsuza kadar `true` kalıyor ve kullanıcı kalıcı "Yükleniyor…" ekranında
// kilitleniyordu (2026-09-10'da yaşandı: asılı bir uvicorn süreci yüzünden `/health`
// hiç sonuçlanmadı, uygulama hiç açılmadı ve hiçbir hata gösterilmedi).
const INIT_TIMEOUT_MS = 10_000

function withTimeout<T>(promise: Promise<T>, label: string): Promise<T> {
  const { promise: guarded, resolve, reject } = Promise.withResolvers<T>()
  const timer = setTimeout(
    () => reject(new Error(`${label} ${INIT_TIMEOUT_MS} ms içinde yanıt vermedi`)),
    INIT_TIMEOUT_MS,
  )
  void promise.then(
    (value) => {
      clearTimeout(timer)
      resolve(value)
    },
    (error: unknown) => {
      clearTimeout(timer)
      reject(error)
    },
  )
  return guarded
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  user: null,
  loading: true,
  saasMode: false,
  failed: false,
  init: async () => {
    set({ loading: true, failed: false })

    let saasMode: boolean
    try {
      // Önceden bu çağrının hatası yutulup `saas_mode: false` varsayılıyordu; backend
      // erişilemezken "yerel mod, oturum açık" gibi davranmak yanlış — her API isteği
      // yine başarısız oluyor, kullanıcı nedenini hiç görmüyor. Artık hata ekranı çıkar.
      saasMode = (await withTimeout(getHealthInfo(), 'Sağlık kontrolü (/health)')).saas_mode
    } catch {
      set({ loading: false, failed: true })
      return
    }

    if (!saasMode || !supabaseClient) {
      // Yerel mod: kimlik doğrulama geçidi yok, her zaman "oturum açık" sayılır.
      set({ saasMode: false, session: null, user: null, loading: false })
      return
    }

    supabaseClient.auth.onAuthStateChange((_event, session) => {
      setAccessToken(session?.access_token ?? null)
      useAuthStore.setState({ session, user: session?.user ?? null })
    })

    try {
      const {
        data: { session },
      } = await withTimeout(supabaseClient.auth.getSession(), 'Oturum kontrolü (Supabase)')
      setAccessToken(session?.access_token ?? null)
      set({ saasMode: true, session, user: session?.user ?? null, loading: false })
    } catch {
      set({ saasMode: true, loading: false, failed: true })
    }
  },
}))
