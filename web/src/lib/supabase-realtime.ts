import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let cachedClient: SupabaseClient | null = null;

export function supabaseRealtimeClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  if (!url || !anonKey) return null;
  if (!cachedClient) {
    cachedClient = createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false }
    });
  }
  return cachedClient;
}
