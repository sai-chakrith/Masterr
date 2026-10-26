"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api, getToken, type TeachingPlan } from "@/lib/api";

export default function LessonPage() {
  const router = useRouter();
  const params = useParams<{ skillId: string }>();
  const skillId = decodeURIComponent(params.skillId);
  const [skill, setSkill] = useState<{ title: string; objective: string | null; lesson: string | null } | null>(null);
  const [plan, setPlan] = useState<TeachingPlan | null>(null);
  const [draft, setDraft] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    void Promise.all([api.curriculum(), api.teaching(skillId)]).then(([catalog, teaching]) => {
      setDraft(catalog.status !== "approved" || !teaching.content_available);
      setSkill(catalog.skills.find((item) => item.id === skillId) ?? null);
      setPlan(teaching);
    }).catch((problem) => {
      if (problem instanceof ApiError && problem.status === 401) router.replace("/login");
      else setError(problem instanceof Error ? problem.message : "Could not load this lesson.");
    });
  }, [router, skillId]);

  async function practise() {
    setBusy(true); setError(null);
    try {
      const session = await api.startPractice(skillId);
      router.push("/session/" + session.session_id);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Could not start practice.");
      setBusy(false);
    }
  }

  if (error) return <p role="alert" className="rounded-lg bg-rose-50 p-3 text-rose-800">{error}</p>;
  if (!skill || !plan) return <p className="text-slate-500">Loading lesson...</p>;
  if (draft) return <section className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
    <h1 className="text-xl font-semibold">This lesson is not published yet</h1>
    <p>A reviewer needs to approve the curriculum before learner-facing teaching is shown.</p>
    <Link className="underline" href="/">Return to your route</Link>
  </section>;

  return <article className="mx-auto max-w-3xl space-y-5 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
    <Link href="/" className="text-sm underline">← Your route</Link>
    <header>
      <p className="text-sm font-medium text-sky-700 dark:text-sky-300">
        {plan.mode === "worked_examples" ? "Start with examples" : plan.mode === "hinted_practice" ? "Guided practice" : "Practice first"}
      </p>
      <h1 className="mt-1 text-3xl font-semibold">{skill.title}</h1>
      {plan.objective && <p className="mt-2 text-slate-600 dark:text-slate-300">{plan.objective}</p>}
    </header>
    {plan.mode === "worked_examples" && <>
      {plan.lesson && <p className="rounded-xl bg-slate-50 p-5 leading-7 dark:bg-slate-800">{plan.lesson}</p>}
      {plan.worked_example && <section className="space-y-2 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
        <h2 className="font-semibold">Worked example</h2>
        <p>{plan.worked_example.prompt}</p>
        <ol className="list-decimal space-y-1 pl-5 text-sm">{plan.worked_example.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
        <p className="text-sm font-medium">Answer: {plan.worked_example.answer}</p>
      </section>}
      {plan.half_worked_example && <section className="space-y-2 rounded-xl border border-sky-200 bg-sky-50 p-5 dark:border-sky-900 dark:bg-sky-950">
        <h2 className="font-semibold">Now you finish one</h2>
        <p>{plan.half_worked_example.prompt}</p>
        <ol className="list-decimal space-y-1 pl-5 text-sm">{plan.half_worked_example.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
        <p className="text-sm font-medium">{plan.half_worked_example.learner_prompt}</p>
      </section>}
    </>}
    {plan.mode === "hinted_practice" && <p className="rounded-xl bg-sky-50 p-5 text-sm leading-6 dark:bg-sky-950">
      Try a fresh question first. You can request a hint while practising.
    </p>}
    {plan.mode === "practice_first" && <p className="rounded-xl bg-sky-50 p-5 text-sm leading-6 dark:bg-sky-950">
      Start with a fresh question. If you miss it, Mastrr will show the reviewed explanation for that item.
    </p>}
    <button onClick={() => void practise()} disabled={busy}
      className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-sky-300 dark:text-slate-950">
      {busy ? "Starting..." : "Start practice"}
    </button>
  </article>;
}
