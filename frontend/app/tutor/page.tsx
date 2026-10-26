"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";

type Part = {
  text: string;
  generated_by: "llm" | "fallback";
  cached: boolean;
  examples?: { question_id: string; answer_checked: boolean }[];
};
type Tutor = { skill_id: string; parts: { lesson: Part; personal: Part } };

async function tutorRequest<T>(path: string, method = "GET"): Promise<T> {
  const response = await fetch(`/api/v1/me/tutor/${path}`, {
    method, headers: { Authorization: `Bearer ${getToken() ?? ""}` }, cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401) throw new Error("Please sign in again.");
    throw new Error(body.error?.message ?? "Tutoring could not be loaded. Try again.");
  }
  return body as T;
}

export default function TutorPage() {
  const router = useRouter();
  const [topics, setTopics] = useState<{ id: string; title: string }[]>([]);
  const [topic, setTopic] = useState("");
  const [result, setResult] = useState<Tutor | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    let current = true;
    void tutorRequest<{ id: string; title: string }[]>("topics").then((items) => {
      if (current) { setTopics(items); setTopic(items[0]?.id ?? ""); }
    }).catch((e: Error) => { if (current) setError(e.message); });
    return () => { current = false; };
  }, [router]);

  async function explain() {
    setBusy(true); setError(""); setResult(null);
    try { setResult(await tutorRequest<Tutor>(encodeURIComponent(topic), "POST")); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load tutoring."); }
    finally { setBusy(false); }
  }

  return <div className="space-y-6">
    <header className="space-y-2">
      <Link href="/" className="text-sm underline">← Your route</Link>
      <h1 className="text-3xl font-semibold">Learn from your mistakes</h1>
      <p className="text-slate-600 dark:text-slate-300">Read the topic lesson, then revisit up to three missed questions from completed sessions.</p>
    </header>
    <form onSubmit={(e) => { e.preventDefault(); void explain(); }} className="flex flex-wrap items-end gap-3">
      <label className="flex grow flex-col gap-1 text-sm">Topic
        <select value={topic} disabled={busy || !topics.length} onChange={(e) => { setTopic(e.target.value); setResult(null); }}
          className="rounded-lg border border-slate-300 bg-white p-3 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
          {topics.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>
      </label>
      <button type="submit" disabled={busy || !topic} className="rounded-lg bg-sky-800 px-4 py-3 font-medium text-white disabled:opacity-50">
        {busy ? "Preparing explanation…" : "Open tutoring"}
      </button>
    </form>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-4 text-rose-800">{error}</p>}
    <div aria-live="polite" aria-busy={busy} className="space-y-5">
      {result && (["lesson", "personal"] as const).map((name) => {
        const part = result.parts[name];
        const checked = part.examples?.filter((item) => item.answer_checked).length ?? 0;
        return <section key={name} className="space-y-3 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
          <h2 className="text-xl font-semibold">{name === "lesson" ? "Topic lesson" : "Your missed questions"}</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {part.generated_by === "llm" ? "AI explanation" : "Fallback explanation"}
            {part.cached && " · Saved explanation"}
          </p>
          {checked > 0 && <p className="text-sm text-emerald-700 dark:text-emerald-300">Final answers checked against the question bank. The working may still contain mistakes.</p>}
          <p className="whitespace-pre-wrap leading-7">{part.text}</p>
        </section>;
      })}
      {result && <p className="text-sm text-slate-600 dark:text-slate-300">Next: practise a fresh question, then try an independent check.</p>}
    </div>
  </div>;
}
