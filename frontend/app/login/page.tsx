"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, api, setToken } from "@/lib/api";

// Local development sign-in. Supabase Auth replaces this before the multi-user pilot.
export default function LoginPage() {
  const router = useRouter();
  const [token, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setToken(token.trim());
    try {
      await api.gaps();
      router.push("/");
    } catch (e) {
      setToken(null);
      setError(e instanceof ApiError && e.status === 401 ? "That token was not accepted." : "The backend is not reachable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="text-sm text-slate-600 dark:text-slate-300">
        Paste the local API token from <code>data/local-api-token</code>. Pilot accounts will sign in with email once
        Supabase is configured.
      </p>
      <input
        type="password"
        value={token}
        onChange={(e) => setValue(e.target.value)}
        aria-label="API token"
        placeholder="Token"
        className="w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
      />
      {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      <button
        type="submit"
        disabled={busy || !token.trim()}
        className="rounded-md bg-slate-900 px-4 py-2 text-white dark:bg-slate-100 dark:text-slate-900"
      >
        {busy ? "Checking..." : "Continue"}
      </button>
    </form>
  );
}
