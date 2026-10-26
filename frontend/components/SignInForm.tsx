"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { authClient, hostedAuthConfigured, localAuthEnabled } from "@/lib/auth-client";

export default function SignInForm() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup" | "recover">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setLocalToken] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const hosted = hostedAuthConfigured();
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const auth = authClient();
      if (!auth) {
        if (!localAuthEnabled()) throw new Error("Account sign-in is not configured yet.");
        setToken(token.trim());
        try { await api.account(); } catch (e) { setToken(null); throw e; }
        router.push("/"); return;
      }
      const callback = window.location.origin + "/auth/callback";
      if (mode === "recover") {
        const { error } = await auth.auth.resetPasswordForEmail(email, { redirectTo: callback + "?next=/account/password" });
        if (error) throw error;
        setMessage("If that email has an account, a password reset link will arrive shortly.");
      } else if (mode === "signup") {
        const { data, error } = await auth.auth.signUp({ email, password, options: { emailRedirectTo: callback } });
        if (error) throw error;
        if (data.session) router.push("/");
        else setMessage("Check your email for the confirmation link, then sign in.");
      } else {
        const { error } = await auth.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed."); }
    finally { setBusy(false); }
  }
  return <section className="mx-auto max-w-md space-y-5">
    <header><h1 className="text-3xl font-semibold">{mode === "signup" ? "Create your account" : mode === "recover" ? "Reset your password" : "Welcome to Mastrr"}</h1>
      <p className="mt-2 text-slate-600 dark:text-slate-300">Choose your goals, understand mistakes, and check what you can do independently.</p></header>
    <form onSubmit={(e) => void submit(e)} className="space-y-4">
      {hosted ? <>
        <label className="block text-sm">Email<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-3" /></label>
        {mode !== "recover" && <label className="block text-sm">Password<input type="password" autoComplete={mode === "signup" ? "new-password" : "current-password"} required minLength={mode === "signup" ? 12 : 1} value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-3" />
          {mode === "signup" && <span className="text-xs text-slate-500">Use at least 12 characters.</span>}</label>}
      </> : <label className="block text-sm">Local development token<input type="password" required value={token} onChange={(e) => setLocalToken(e.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-3" />
        <span className="text-xs text-slate-500">Available only with local development enabled on localhost.</span></label>}
      {error && <p role="alert" className="text-sm text-rose-700 dark:text-rose-300">{error}</p>}
      {message && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{message}</p>}
      <button disabled={busy} className="w-full rounded-lg bg-sky-800 p-3 font-medium text-white disabled:opacity-50">{busy ? "Please wait…" : mode === "signup" ? "Create account" : mode === "recover" ? "Send reset link" : "Sign in"}</button>
    </form>
    {hosted && <div className="flex flex-wrap gap-4 text-sm">
      {(["login", "signup", "recover"] as const).filter((item) => item !== mode).map((item) => <button key={item} className="underline" onClick={() => { setMode(item); setError(""); setMessage(""); setPassword(""); }}>{item === "login" ? "Sign in" : item === "signup" ? "Create account" : "Forgot password?"}</button>)}
    </div>}
    <p className="text-xs text-slate-500">Learning scores are provisional estimates. <Link href="/privacy" className="underline">How your data is used</Link></p>
  </section>;
}
