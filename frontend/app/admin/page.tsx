"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, request } from "@/lib/api";

type Item = { id: string; skill_id: string; status: string; hidden: boolean; prompt: string; purpose: string };
type Review = { id?: string; key?: string; checksum: string; status?: string; document: Record<string, unknown> };
type Report = { id: string; question_id: string; message: string; status: string; resolution: string };

export default function AdminPage() {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [topics, setTopics] = useState<{ id: string; title: string }[]>([]);
  const [skill, setSkill] = useState("");
  const [status, setStatus] = useState("draft");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<Item[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [editor, setEditor] = useState("");
  const [saved, setSaved] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [docKey, setDocKey] = useState("curriculum");

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    void api.account().then(async (account) => {
      if (!account.content_reviewer) throw new Error("Your account does not have content-reviewer access.");
      setAllowed(true); const catalog = await api.curriculum(); setTopics(catalog.skills);
    }).catch((e: Error) => setError(e.message));
  }, [router]);

  const load = useCallback(async () => {
    if (!allowed) return;
    const params = new URLSearchParams({ offset: String(offset), limit: "20" });
    if (skill) params.set("skill", skill);
    if (status) params.set("status", status);
    try {
      const [list, reported] = await Promise.all([
        request<{ total: number; items: Item[] }>("/v1/admin/questions?" + params),
        request<Report[]>("/v1/admin/reports"),
      ]);
      setTotal(list.total); setItems(list.items); setReports(reported);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load review queue."); }
  }, [allowed, skill, status, offset]);
  useEffect(() => { void load(); }, [load]);

  function show(value: Review) {
    const text = JSON.stringify(value.document, null, 2);
    setReview(value); setEditor(text); setSaved(text); setConfirmed(false); setNote("");
  }
  async function open(path: string) {
    setBusy(true); setError(""); setMessage("");
    try { show(await request<Review>(path)); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load content."); }
    finally { setBusy(false); }
  }
  async function decide(action: "save" | "approve" | "withdraw") {
    if (!review) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const path = review.id ? "/v1/admin/questions/" + encodeURIComponent(review.id)
        : "/v1/admin/documents/" + encodeURIComponent(review.key!);
      const result = await request<Review>(path, { method: "POST", body: JSON.stringify({
        action, expected_checksum: review.checksum, note, confirm_reviewed: confirmed,
        ...(action === "save" ? { document: JSON.parse(editor) } : {}),
      }) });
      show(result); setMessage(action === "save" ? "Saved as a new draft. Review the saved version before publishing." : action === "approve" ? "Published with your authenticated reviewer identity." : "Withdrawn. Previous attempts remain in the history.");
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not apply decision."); }
    finally { setBusy(false); }
  }
  async function resolve(report: Report) {
    if (note.trim().length < 10) { setError("Enter a resolution of at least ten characters in the review note."); return; }
    setBusy(true); setError("");
    try {
      await request("/v1/admin/reports/" + report.id + "/resolve", { method: "POST", body: JSON.stringify({ resolution: note }) });
      await load(); setMessage("Report resolved with your note.");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not resolve report."); }
    finally { setBusy(false); }
  }
  const preview = review?.document;
  return <div className="space-y-7">
    <header className="space-y-2"><Link href="/account" className="text-sm underline">← Account</Link><h1 className="text-3xl font-semibold">Content review</h1>
      <p className="text-sm text-slate-600 dark:text-slate-300">Saving creates a draft. Publishing requires your review of the exact saved content. Hidden validation items remain private to reviewers.</p></header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-rose-800">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-900">{message}</p>}
    {allowed && <>
      <section className="space-y-3"><h2 className="text-xl font-semibold">Curriculum, notes and exam profiles</h2>
        <div className="flex flex-wrap gap-3"><select aria-label="Content document" value={docKey} onChange={(e) => setDocKey(e.target.value)} className="max-w-full rounded-lg border bg-transparent p-2">
          <option value="curriculum">Curriculum and worked examples</option><option value="misconceptions">Misconceptions and fixes</option><option value="exam-profiles">Exam profiles</option>
          {topics.map((t) => <option key={t.id} value={"notes:" + t.id}>{t.title} notes</option>)}
        </select><button disabled={busy} onClick={() => void open("/v1/admin/documents/" + encodeURIComponent(docKey))} className="rounded-lg border px-3 py-2">Review document</button></div>
      </section>
      {review && <section className="space-y-4 rounded-xl border p-5">
        <h2 className="text-xl font-semibold">Reviewing {review.id ?? review.key}</h2>
        {typeof preview?.prompt === "string" && <div className="space-y-2 leading-7"><p>{preview.prompt}</p><p>Stored answer: {String(preview.answer)}</p><p>{String(preview.solution)}</p></div>}
        {typeof preview?.text === "string" && <p className="whitespace-pre-wrap text-sm leading-6">{preview.text}</p>}
        <label className="block text-sm">Content JSON<textarea value={editor} onChange={(e) => { setEditor(e.target.value); setConfirmed(false); }} spellCheck={false} rows={14} className="mt-1 w-full rounded-lg border bg-transparent p-3 font-mono text-xs" /></label>
        <label className="block text-sm">Review note or report resolution<textarea value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} rows={2} className="mt-1 w-full rounded-lg border bg-transparent p-2" /></label>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={editor !== saved} onChange={(e) => setConfirmed(e.target.checked)} />I personally checked the method, answer, wording and any distractors in this saved version.</label>
        <div className="flex flex-wrap gap-3"><button disabled={busy || editor === saved} onClick={() => void decide("save")} className="rounded-lg border px-4 py-2 disabled:opacity-50">Save edits as draft</button>
          <button disabled={busy || !confirmed || editor !== saved} onClick={() => void decide("approve")} className="rounded-lg bg-sky-800 px-4 py-2 text-white disabled:opacity-50">Publish reviewed content</button>
          <button disabled={busy || editor !== saved || note.trim().length < 10} onClick={() => void decide("withdraw")} className="rounded-lg border px-4 py-2 disabled:opacity-50">Withdraw</button></div>
      </section>}
      <section className="space-y-3"><h2 className="text-xl font-semibold">Question queue</h2>
        <div className="flex flex-wrap gap-3"><select aria-label="Question topic" value={skill} onChange={(e) => { setSkill(e.target.value); setOffset(0); }} className="max-w-full rounded-lg border bg-transparent p-2"><option value="">All topics</option>{topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}</select>
          <select aria-label="Question status" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="rounded-lg border bg-transparent p-2"><option value="draft">Draft</option><option value="approved">Approved</option><option value="withdrawn">Withdrawn</option><option value="">All statuses</option></select></div>
        <p className="text-sm">{total} matching questions</p>
        <ul className="divide-y">{items.map((item) => <li key={item.id} className="space-y-2 py-3"><p className="text-xs text-slate-500">{item.id} · {item.purpose} · {item.status}{item.hidden && " · Hidden validation"}</p><p>{item.prompt}</p>
          <button disabled={busy} onClick={() => void open("/v1/admin/questions/" + encodeURIComponent(item.id))} className="text-sm underline">Review question</button></li>)}</ul>
        <div className="flex gap-3"><button disabled={!offset || busy} onClick={() => setOffset(Math.max(0, offset - 20))} className="rounded-lg border px-3 py-2 disabled:opacity-50">Previous</button><button disabled={offset + 20 >= total || busy} onClick={() => setOffset(offset + 20)} className="rounded-lg border px-3 py-2 disabled:opacity-50">Next</button></div>
      </section>
      <section className="space-y-3"><h2 className="text-xl font-semibold">Learner reports</h2>
        {reports.length === 0 ? <p className="text-sm">No reports have been submitted.</p> : <ul className="divide-y">{reports.map((r) => <li key={r.id} className="space-y-2 py-3"><p className="text-xs">{r.question_id} · {r.status}</p><p>{r.message}</p>{r.resolution && <p>{r.resolution}</p>}<div className="flex gap-3"><button onClick={() => void open("/v1/admin/questions/" + encodeURIComponent(r.question_id))} className="underline">Inspect question</button>{r.status === "open" && <button disabled={busy} onClick={() => void resolve(r)} className="underline">Resolve using review note</button>}</div></li>)}</ul>}
      </section>
    </>}
  </div>;
}
