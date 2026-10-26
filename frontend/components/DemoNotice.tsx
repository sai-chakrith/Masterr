"use client";
import { useEffect, useState } from "react";
export default function DemoNotice() {
  const [runtime, setRuntime] = useState<{ demo: boolean; ai_configured: boolean } | null>(null);
  useEffect(() => { void fetch("/api/runtime", { cache: "no-store" }).then((r) => r.ok ? r.json() : null).then(setRuntime).catch(() => undefined); }, []);
  if (!runtime?.demo) return null;
  return <aside role="note" className="border-b border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
    <div className="mx-auto max-w-3xl"><strong>Demonstration only.</strong> Sample content and scores are not human-reviewed or real learner evidence.
      {runtime.ai_configured ? " Live AI is configured; each explanation labels its actual source." : " AI is offline; tutoring uses labelled notes and recorded answers."}</div>
  </aside>;
}
