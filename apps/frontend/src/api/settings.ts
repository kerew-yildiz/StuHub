import { apiFetch } from './client'

/** Ayarlar sözlüğü (gizli anahtarlar backend'de maskelenir). */
export type SettingsMap = Record<string, string>

export const settingsApi = {
  list: () => apiFetch<SettingsMap>('/settings'),
  set: (key: string, value: string) =>
    apiFetch<{ ok: boolean }>('/settings', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),
}
