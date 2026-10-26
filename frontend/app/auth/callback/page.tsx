"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";
let pending: Promise<string> | null = null;
function finish() {
  if (!pending) pending = (async () => {
    const client = authClient();
    if (!client) throw new Error("Account sign-in is not configured.");
    const params = new URLSearchParams(window.location.search);
    window.history.replaceState({}, "", "/auth/callback");
    const code = params.get("code"), hash = params.get("token_hash"), type = params.get("type");
    const next = params.get("next") === "/account/password" || type === "recovery" ? "/account/password" : "/";
    if (params.get("error")) throw new Error("This email link is expired or invalid. Request a new link.");
    const result = code ? await client.auth.exchangeCodeForSession(code)
      : hash && (type === "recovery" || type === "signup" || type === "email")
        ? await client.auth.verifyOtp({ token_hash: hash, type }) : await client.auth.getSession();
    if (result.error) throw result.error;
    if (!result.data.session) throw new Error("No sign-in session was returned. Request a new link.");
    return next;
  })();
  return pending;
}
export default function CallbackPage() {
  const [error, setError] = useState("");
  const router = useRouter();
  useEffect(() => { void finish().then((next) => router.replace(next)).catch((e: Error) => setError(e.message)); }, [router]);
  return <section className="space-y-3"><h1 className="text-2xl font-semibold">Completing sign-in</h1>
    {error ? <><p role="alert">{error}</p><Link href="/login" className="underline">Return to sign in</Link></> : <p>Verifying your email link…</p>}</section>;
}
