import type { Session, User } from '@supabase/supabase-js'
import { create } from 'zustand'

import { getHealthInfo, setAccessToken } from '../api/client'
import { supabaseClient } from '../lib/supabaseClient'

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
  saasMode: boolean
  init: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  session: null,
  user: null,
  loading: true,
  saasMode: false,
  init: async () => {
    const health = await getHealthInfo().catch(() => ({ saas_mode: false }))
    const saasMode = health.saas_mode

    if (!saasMode || !supabaseClient) {
      // Yerel mod: kimlik doğrulama geçidi yok, her zaman "oturum açık" sayılır.
      set({ saasMode: false, session: null, user: null, loading: false })
      return
    }

    supabaseClient.auth.onAuthStateChange((_event, session) => {
      setAccessToken(session?.access_token ?? null)
      useAuthStore.setState({ session, user: session?.user ?? null })
    })

    const {
      data: { session },
    } = await supabaseClient.auth.getSession()
    setAccessToken(session?.access_token ?? null)
    set({ saasMode: true, session, user: session?.user ?? null, loading: false })
  },
}))
