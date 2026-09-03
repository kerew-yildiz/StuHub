import { apiFetch } from './client'

/** Ayarlar sözlüğü (gizli anahtarlar backend'de maskelenir). */
export type SettingsMap = Record<string, string>

/** Ücretsiz LLM sağlayıcı zincirindeki tek bir sağlayıcının durumu. */
export type LLMProviderStatus = {
  name: string
  label: string
  configured: boolean
  cooldown_until: string | null
  active: boolean
}

export const settingsApi = {
  list: () => apiFetch<SettingsMap>('/settings'),
  set: (key: string, value: string) =>
    apiFetch<{ ok: boolean }>('/settings', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),
  llmStatus: () => apiFetch<LLMProviderStatus[]>('/settings/llm-status'),
}
