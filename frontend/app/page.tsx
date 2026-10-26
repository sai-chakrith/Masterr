"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { TopicCard } from "@/components/TopicCard";
import { ApiError, api, getToken, type Topic } from "@/lib/api";
import { STATUS } from "@/lib/labels";

// C4 roadmap: topics in prerequisite order with their state, score and next step.
export default function RoadmapPage() {
  const router = useRouter();
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [gaps, today] = await Promise.all([api.gaps(), api.today()]);
      setTopics(gaps);
      setActive(today.active_session_id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError("The backend is not reachable. Start it with scripts/start-local.ps1.");
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else load();
  }, [load, router]);

  async function start(kind: "diagnostic" | "retest" | "validation", skill: string) {
    setBusy(true);
    setError(null);
    try {
      const created =
        kind === "diagnostic"
          ? await api.startDiagnostic(skill)
          : kind === "retest"
            ? await api.startRetest(skill)
            : await api.startValidation(skill);
      router.push(`/session/${created.session_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  if (!topics) {
    return <p className="text-slate-500">{error ?? "Loading your roadmap..."}</p>;
  }
  const titles = Object.fromEntries(topics.map((t) => [t.skill_id, t.title]));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Numbers roadmap</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Mastered means you solve about 75% of typical questions on a topic.
        </p>
      </div>
      {active && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-sky-50 p-3 text-sm dark:bg-sky-950">
          <span>You have a session in progress.</span>
          <Link href={`/session/${active}`} className="font-medium text-sky-700 underline dark:text-sky-300">
            Resume
          </Link>
        </div>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800 dark:bg-rose-950 dark:text-rose-200">
          {error}
        </p>
      )}
      <ul className="relative space-y-4 before:absolute before:bottom-4 before:left-[7px] before:top-4 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
        {topics.map((topic) => (
          <TopicCard key={topic.skill_id} topic={topic} titles={titles} busy={busy} locked={!!active} onStart={start} />
        ))}
      </ul>
      <ul className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-400" aria-label="Legend">
        {Object.entries(STATUS).map(([key, s]) => (
          <li key={key} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${s.node}`} />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
