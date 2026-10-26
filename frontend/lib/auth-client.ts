"use client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
let client: SupabaseClient | null = null;
export const SESSION_KEY = "mastrr-auth-session";
export function hostedAuthConfigured() {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
}
export function localAuthEnabled() {
  return process.env.NEXT_PUBLIC_LOCAL_DEVELOPMENT === "1" && typeof window !== "undefined"
    && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
}
export function authClient() {
  if (!hostedAuthConfigured()) return null;
  if (!client) client = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!, {
    auth: { storageKey: SESSION_KEY, persistSession: true, autoRefreshToken: true,
      detectSessionInUrl: false, flowType: "pkce" },
  });
  return client;
}
export function savedToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    if (hostedAuthConfigured()) {
      const saved = JSON.parse(window.localStorage.getItem(SESSION_KEY) ?? "null");
      return typeof saved?.access_token === "string" ? saved.access_token : null;
    }
    return localAuthEnabled() ? window.localStorage.getItem("mastrr-token") : null;
  } catch { return null; }
}
export async function accessToken(): Promise<string | null> {
  const supabase = authClient();
  if (!supabase) return savedToken();
  const { data, error } = await supabase.auth.getSession();
  if (error) throw new Error("Your session could not be refreshed. Sign in again.");
  return data.session?.access_token ?? null;
}
export async function signOut() {
  const supabase = authClient();
  try {
    if (supabase) {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    }
  } finally {
    window.localStorage.removeItem("mastrr-token");
    window.localStorage.removeItem(SESSION_KEY);
  }
}
