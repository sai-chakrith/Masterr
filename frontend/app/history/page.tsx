"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { request } from "@/lib/api";
type Session = { id: string; skill_id: string; mode: string; status: string; created_at: string };
export default function HistoryPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { void request<Session[]>("/v1/me/history").then(setSessions).catch((e: Error) => setError(e.message)).finally(() => setLoaded(true)); }, []);
  return <section className="space-y-5"><h1 className="text-3xl font-semibold">Your learning history</h1>
    <p>Resume an unfinished activity or revisit a completed session. <Link href="/practice-test" className="underline">Timed practice results</Link></p>
    {error && <p role="alert">{error}</p>}{!loaded && <p>Loading history…</p>}
    {loaded && !sessions.length && !error && <p>Your first activity will appear here after you choose a topic.</p>}
    <ul className="divide-y">{sessions.map((s) => <li key={s.id} className="flex flex-wrap justify-between gap-3 py-4"><div><p className="font-medium">{s.skill_id} · {s.mode}</p><p className="text-sm text-slate-500">{new Date(s.created_at).toLocaleString()} · {s.status}</p></div><Link href={"/session/" + s.id} className="underline">{s.status === "active" || s.status === "assisted" ? "Resume" : "View session"}</Link></li>)}</ul>
  </section>;
}
