"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "@/lib/api";
type View = { id: string; status: string; question_count: number; answered: number; deadline: string; server_time: string;
  question: { id: string; prompt: string; skill_id: string; options: { id: string; text: string }[] } | null;
  correct?: number; outcomes?: { question: string; skill_id: string; answered: boolean; correct: boolean; solution: string }[] };
export default function TimedRunPage() {
  const { id } = useParams<{ id: string }>();
  const [view, setView] = useState<View | null>(null);
  const [answer, setAnswer] = useState("");
  const [option, setOption] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const timing = useRef({ deadline: 0, offset: 0, expired: false });
  const route = "/v1/me/timed-tests/" + id;
  const display = useCallback((data: View) => {
    setView(data); setAnswer(""); setOption("");
    timing.current = { deadline: Date.parse(data.deadline), offset: Date.now() - Date.parse(data.server_time), expired: false };
    setSeconds(Math.max(0, Math.ceil((Date.parse(data.deadline) - Date.parse(data.server_time)) / 1000)));
  }, []);
  const load = useCallback(async () => { try { display(await request<View>(route)); } catch (e) { setError(e instanceof Error ? e.message : "Could not load timed practice."); } }, [display, route]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (view?.status !== "active") return;
    const timer = window.setInterval(() => {
      const t = timing.current; const left = Math.max(0, Math.ceil((t.deadline - (Date.now() - t.offset)) / 1000));
      setSeconds(left);
      if (!left && !t.expired) { t.expired = true; void load(); }
    }, 500);
    return () => window.clearInterval(timer);
  }, [view?.status, load]);
  async function send(dontKnow: boolean) {
    if (!view?.question) return;
    setBusy(true); setError("");
    try { display(await request<View>(route + "/answers", { method: "POST", body: JSON.stringify({ question_id: view.question.id,
      answer: dontKnow || view.question.options.length ? "" : answer, option_id: dontKnow ? null : option || null, dont_know: dontKnow }) })); }
    catch (e) { setError(e instanceof Error ? e.message : "Your answer was not saved. Try again."); }
    finally { setBusy(false); }
  }
  async function finish() {
    if (!window.confirm("Finish this test? Unanswered questions will count as incorrect.")) return;
    setBusy(true); setError("");
    try { display(await request<View>(route + "/finish", { method: "POST" })); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not finish the test."); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5"><h1 className="text-3xl font-semibold">Timed practice</h1>
    {error && <p role="alert" className="text-rose-700 dark:text-rose-300">{error}</p>}
    {view?.status === "completed" ? <>
      <p className="rounded-xl border p-5 text-xl">{view.correct} of {view.question_count} correct · {view.answered} answered</p>
      <p className="text-sm">This practice result does not change your diagnostic or mastery status.</p>
      {view.outcomes?.map((o, i) => <section key={i} className="space-y-2 border-t pt-4"><h2 className="font-semibold">{i + 1}. {o.question}</h2><p className="text-sm">{!o.answered ? "Unanswered" : o.correct ? "Correct" : "Needs review"}</p><p>{o.solution}</p><Link href={"/tutor?topic=" + encodeURIComponent(o.skill_id)} className="text-sm underline">Study this topic</Link></section>)}
      <Link href="/practice-test" className="block underline">Return to timed practice</Link>
    </> : <>
      {view && <p role="timer" aria-label="Time remaining">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")} remaining · {view.answered} of {view.question_count} answered</p>}
      {view?.question && <form onSubmit={(e) => { e.preventDefault(); void send(false); }} className="space-y-4">
        <p className="text-xl leading-8">{view.question.prompt}</p>
        {view.question.options.length > 0 ? <fieldset className="space-y-3"><legend className="mb-2 text-sm">Choose an answer</legend>{view.question.options.map((o) => <label key={o.id} className="flex gap-2 rounded-lg border p-3"><input type="radio" name="answer" required checked={option === o.id} onChange={() => setOption(o.id)} />{o.text}</label>)}</fieldset>
          : <label className="block text-sm">Your answer<input inputMode="numeric" required value={answer} onChange={(e) => setAnswer(e.target.value)} className="ml-3 rounded-lg border bg-transparent p-3" /></label>}
        <div className="flex gap-3"><button disabled={busy || seconds <= 0} className="rounded-lg bg-sky-800 px-4 py-2 text-white disabled:opacity-50">Save answer</button><button type="button" disabled={busy || seconds <= 0} onClick={() => void send(true)} className="rounded-lg border px-4 py-2">I don&apos;t know</button></div>
      </form>}
      <button disabled={busy} onClick={() => void finish()} className="text-sm underline">Finish test</button>
    </>}
  </div>;
}
