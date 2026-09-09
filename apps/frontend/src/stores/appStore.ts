import { useEffect } from 'react'
import { create } from 'zustand'

import { getHealth } from '../api/client'

export type HealthStatus = 'checking' | 'ok' | 'down'

interface AppState {
  health: HealthStatus
  setHealth: (status: HealthStatus) => void
}

export const useAppStore = create<AppState>((set) => ({
  health: 'checking',
  setHealth: (health) => set({ health }),
}))

const POLL_INTERVAL_MS = 5000

/** Backend sağlığını 5 saniyede bir yoklar (yol haritası 2.2.4). */
export function useHealthPolling(): HealthStatus {
  const health = useAppStore((s) => s.health)

  useEffect(() => {
    let cancelled = false
    // Backend yavaşladığında 5sn'lik tetikleyici, uçuştaki isteği beklemeden yenisini
    // ekliyordu: tarayıcının origin başına 6 bağlantısı dolduğunda kuyruk hiç boşalmıyor.
    let inFlight = false

    const check = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const ok = await getHealth()
        if (!cancelled) {
          useAppStore.getState().setHealth(ok ? 'ok' : 'down')
        }
      } finally {
        inFlight = false
      }
    }

    void check()
    const id = setInterval(check, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return health
}
