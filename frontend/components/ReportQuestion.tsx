"use client";
import { useState } from "react";
import { api } from "@/lib/api";
export default function ReportQuestion({ assignmentId }: { assignmentId: string }) {
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try { await api.reportQuestion(assignmentId, text); setText(""); setMessage("Report saved for a reviewer."); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not save report."); }
    finally { setBusy(false); }
  }
  return <details className="text-sm"><summary className="cursor-pointer underline">Report a problem with this question</summary>
    <form onSubmit={(e) => void submit(e)} className="mt-3 space-y-2"><label className="block">Describe the issue<textarea required minLength={10} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} className="mt-1 block w-full rounded-lg border bg-transparent p-2" /></label><button disabled={busy || text.trim().length < 10} className="rounded-lg border px-3 py-2 disabled:opacity-50">Send report</button><p role="status">{message}</p></form>
  </details>;
}
