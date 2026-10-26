"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import { signOut } from "@/lib/auth-client";

export default function AccountPage() {
  const router = useRouter();
  const [account, setAccount] = useState<Awaited<ReturnType<typeof api.account>> | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleted, setDeleted] = useState(false);
  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    void api.account().then(setAccount).catch((e: Error) => setError(e.message));
  }, [router]);
  async function download() {
    setBusy(true); setError("");
    try {
      const data = await api.exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = "mastrr-learning-data.json"; link.click();
      URL.revokeObjectURL(url); setMessage("Your learning-data export was downloaded.");
    } catch (e) { setError(e instanceof Error ? e.message : "Export failed."); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (confirmation !== "DELETE") return;
    setBusy(true); setError("");
    try {
      const result = await api.deleteAccount();
      setDeleted(true); setMessage(result.message);
      try { await signOut(); } catch { window.localStorage.removeItem("mastrr-token"); window.localStorage.removeItem("mastrr-auth-session"); }
    } catch (e) { setError(e instanceof Error ? e.message : "Account deletion failed."); }
    finally { setBusy(false); }
  }
  if (deleted) return <section className="space-y-3"><h1 className="text-2xl font-semibold">Account removed</h1><p role="status">{message}</p><Link href="/login" className="underline">Return to sign in</Link></section>;
  return <div className="space-y-7">
    <h1 className="text-3xl font-semibold">Your account</h1>
    {error && <p role="alert" className="text-rose-700 dark:text-rose-300">{error}</p>}
    {message && <p role="status">{message}</p>}
    {account && <>
      <section className="space-y-3"><h2 className="text-xl font-semibold">Account controls</h2>
        {account.local_development ? <p className="text-sm">Local developer account. Hosted email accounts are not enabled in this environment.</p> : <Link href="/account/password" className="underline">Change password</Link>}
        {account.content_reviewer && <p><Link href="/admin" className="underline">Open content review</Link></p>}
      </section>
      <section className="space-y-2 rounded-xl border p-5"><h2 className="text-xl font-semibold">AI tutoring allowance</h2>
        <p>{account.tutor_usage.calls} of {account.tutor_usage.daily_call_limit} model calls reserved for {account.tutor_usage.period} (UTC).</p>
        <p className="text-sm text-slate-500">Retries count as calls. Saved explanations use no model calls.</p>
      </section>
      <section className="space-y-3"><h2 className="text-xl font-semibold">Your learning data</h2>
        <p>Download your goals, sessions, answers, explanations and learning history. Finish or abandon an active activity first.</p>
        <button disabled={busy} onClick={() => void download()} className="rounded-lg border px-4 py-2 disabled:opacity-50">Download my data</button>
        <p><Link href="/privacy" className="text-sm underline">Data use and deletion details</Link></p>
      </section>
      <section className="space-y-3 border-t pt-5"><h2 className="text-xl font-semibold">Delete account</h2>
        <p>This removes your learning data and disables this identity. Published reviewer attribution and a minimal deletion record are retained.</p>
        <label className="block text-sm">Type DELETE to confirm<input value={confirmation} onChange={(e) => setConfirmation(e.target.value)} autoComplete="off" className="mt-1 block rounded-lg border bg-transparent p-2" /></label>
        <button disabled={busy || confirmation !== "DELETE"} onClick={() => void remove()} className="rounded-lg bg-rose-800 px-4 py-2 text-white disabled:opacity-50">Delete my account</button>
      </section>
    </>}
  </div>;
}
