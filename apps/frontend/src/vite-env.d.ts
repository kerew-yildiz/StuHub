/// <reference types="vite/client" />

/** Derleme kimliği — vite.config.ts `define` ile gömülür (sürüm+kısa commit). */
declare const __STUHUB_BUILD__: string

interface Window {
  /** Çalışan build'in kimliği (src/lib/pwa-update.ts yazar) — teşhis/doğrulama. */
  __STUHUB_SURUM__?: string
}

interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_ANON_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
