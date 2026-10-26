"use client";
import Link from "next/link";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";
export default function PasswordPage() {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      if (password !== repeat) throw new Error("The passwords do not match.");
      const client = authClient();
      if (!client) throw new Error("Hosted account sign-in is not configured.");
      const session = await client.auth.getSession();
      if (!session.data.session) throw new Error("Open a new reset link or sign in before changing your password.");
      const { error } = await client.auth.updateUser({ password });
      if (error) throw error;
      setPassword(""); setRepeat(""); setMessage("Your password was updated.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update password."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={(e) => void submit(e)} className="mx-auto max-w-md space-y-4">
    <h1 className="text-2xl font-semibold">Set a new password</h1>
    <label className="block text-sm">New password<input type="password" required minLength={12} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-3" /></label>
    <label className="block text-sm">Repeat password<input type="password" required minLength={12} autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-3" /></label>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <button disabled={busy} className="rounded-lg bg-sky-800 px-4 py-2 text-white disabled:opacity-50">Update password</button>
    <p><Link href="/account" className="underline">Return to account</Link></p>
  </form>;
}
