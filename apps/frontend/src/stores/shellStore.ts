import { create } from 'zustand'

/**
 * Shell durumu — iki fullscreen kavramı kesinlikle ayrıdır (yönerge §25-28):
 *
 * - `browserFullscreen`: tarayıcının F11 benzeri Fullscreen API'si (header kontrolü).
 *   Sidebar/header görünür kalır; yalnızca browser chrome'u kalkar.
 * - `workspaceFullscreen`: workspace'in kendi kontrolü. Shell (sidebar + header)
 *   gizlenir, workspace tüm uygulama alanına yayılır; browser chrome kalır.
 *
 * Focus Mode bunlardan ikisinden de ayrıdır: shell görünürken workspace'in ana
 * content alanını kaplamasıdır ve workspace açılışında otomatiktir.
 */
interface ShellState {
  workspaceFullscreen: boolean
  browserFullscreen: boolean
  setWorkspaceFullscreen: (value: boolean) => void
  toggleWorkspaceFullscreen: () => void
  setBrowserFullscreen: (value: boolean) => void
}

export const useShellStore = create<ShellState>((set) => ({
  workspaceFullscreen: false,
  browserFullscreen: false,
  setWorkspaceFullscreen: (value) => set({ workspaceFullscreen: value }),
  toggleWorkspaceFullscreen: () => set((s) => ({ workspaceFullscreen: !s.workspaceFullscreen })),
  setBrowserFullscreen: (value) => set({ browserFullscreen: value }),
}))
