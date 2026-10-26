"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, request } from "@/lib/api";
type Run = { id: string; status: string; created_at: string; question_count: number };
export default function PracticeTestPage() {
  const router = useRouter();
  const [topics, setTopics] = useState<{ id: string; title: string }[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [count, setCount] = useState(10);
  const [minutes, setMinutes] = useState(15);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    void Promise.all([api.curriculum(), request<Run[]>("/v1/me/timed-tests")]).then(([catalog, history]) => { setTopics(catalog.skills); setRuns(history); })
      .catch((e: Error) => setError(e.message));
  }, [router]);
  async function start(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const result = await request<{ id: string }>("/v1/me/timed-tests", { method: "POST", body: JSON.stringify({ skill_ids: selected, question_count: count, minutes }) });
      router.push("/practice-test/" + result.id);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not start timed practice."); }
    finally { setBusy(false); }
  }
  return <div className="space-y-6"><header><h1 className="text-3xl font-semibold">Timed mixed practice</h1><p className="mt-2 text-slate-600 dark:text-slate-300">Use fresh reviewed practice questions. This is not an official exam simulation and does not change your mastery decisions.</p></header>
    {error && <p role="alert" className="text-rose-700 dark:text-rose-300">{error}</p>}
    {runs.some((r) => r.status === "active") && <p className="rounded-lg border p-3">You have an unfinished test. <Link className="underline" href={"/practice-test/" + runs.find((r) => r.status === "active")!.id}>Resume timed practice</Link></p>}
    <form onSubmit={(e) => void start(e)} className="space-y-4"><fieldset className="space-y-2"><legend className="mb-2 font-medium">Choose topics</legend>
      {topics.map((t) => <label key={t.id} className="flex gap-2 text-sm"><input type="checkbox" checked={selected.includes(t.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, t.id] : selected.filter((s) => s !== t.id))} />{t.title}</label>)}
    </fieldset><div className="flex flex-wrap gap-5"><label className="text-sm">Questions<input type="number" min={Math.max(3, selected.length)} max={30} value={count} onChange={(e) => setCount(Number(e.target.value))} className="ml-2 w-20 rounded-lg border bg-transparent p-2" /></label>
      <label className="text-sm">Minutes<input type="number" min={1} max={120} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="ml-2 w-20 rounded-lg border bg-transparent p-2" /></label></div>
      <button disabled={busy || !selected.length || runs.some((r) => r.status === "active")} className="rounded-lg bg-sky-800 px-4 py-3 text-white disabled:opacity-50">Start timed practice</button>
    </form>
    {runs.length > 0 && <section className="space-y-3"><h2 className="text-xl font-semibold">Previous tests</h2><ul className="divide-y">{runs.map((r) => <li key={r.id} className="flex flex-wrap justify-between gap-3 py-3"><span>{new Date(r.created_at).toLocaleString()} · {r.question_count} questions · {r.status}</span><Link href={"/practice-test/" + r.id} className="underline">{r.status === "active" ? "Resume" : "View result"}</Link></li>)}</ul></section>}
  </div>;
}
