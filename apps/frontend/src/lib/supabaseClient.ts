import { createClient, type SupabaseClient } from '@supabase/supabase-js'

/** SaaS modda Supabase Auth için istemci. Yerel modda env değişkenleri yoksa
 * `null` döner — tüketiciler bu durumu ele almalı (yerel modda hiç kullanılmaz). */
export const supabaseClient: SupabaseClient | null = (() => {
  const url = import.meta.env.VITE_SUPABASE_URL
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY
  if (!url || !anonKey) {
    return null
  }
  return createClient(url, anonKey)
})()
