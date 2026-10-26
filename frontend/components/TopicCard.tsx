"use client";

import Link from "next/link";
import type { Topic } from "@/lib/api";
import { STATUS, scoreLine } from "@/lib/labels";

interface Props {
  topic: Topic;
  titles: Record<string, string>;
  busy: boolean;
  locked: boolean;
  onStart: (kind: "diagnostic" | "retest" | "validation", skill: string) => void;
}

export function TopicCard({ topic, titles, busy, locked, onStart }: Props) {
  const status = STATUS[topic.status];
  const line = scoreLine(topic);
  const pct = topic.score === null ? null : Math.round(topic.score * 100);
  const bar = Math.round(topic.mastery_bar * 100);
  const disabled = busy || locked;
  const button =
    "rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900";

  return (
    <li className="relative pl-8">
      <span
        aria-hidden
        data-status={topic.status}
        className={`absolute left-0 top-5 h-4 w-4 rounded-full ring-4 ring-white dark:ring-slate-950 ${status.node}`}
      />
      <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">{topic.title}</h2>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.chip}`}>{status.label}</span>
        </div>
        {topic.prerequisites.length > 0 && (
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Builds on {topic.prerequisites.map((p) => titles[p] ?? p).join(", ")}
          </p>
        )}
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{status.blurb}</p>
        {line && (
          <div className="mt-3">
            <p className="text-sm font-medium" data-testid="score-line">
              {line}
            </p>
            {pct !== null && (
              <div
                className="relative mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800"
                role="meter"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Score ${pct}%, mastery bar ${bar}%`}
              >
                <div
                  className={`h-2 rounded-full ${pct >= bar ? "bg-emerald-500" : "bg-sky-500"}`}
                  style={{ width: `${pct}%` }}
                />
                <div
                  className="absolute -top-1 h-4 w-0.5 bg-slate-500"
                  style={{ left: `${bar}%` }}
                  title={`Mastery bar: ${bar}%`}
                />
              </div>
            )}
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {topic.status === "unassessed" && (
            <button className={button} disabled={disabled} onClick={() => onStart("diagnostic", topic.skill_id)}>
              Start diagnostic
            </button>
          )}
          {topic.status === "borderline" && topic.source_session_id && (
            <Link className={button} href={`/review/${topic.source_session_id}`}>
              Review missed questions
            </Link>
          )}
          {(topic.status === "gap" || topic.status === "borderline") && (
            <button className={button} disabled={disabled} onClick={() => onStart("retest", topic.skill_id)}>
              Take the retest
            </button>
          )}
          <button
            className="px-1 text-xs text-slate-500 underline-offset-2 hover:underline dark:text-slate-400"
            disabled={disabled}
            onClick={() => onStart("validation", topic.skill_id)}
          >
            Pilot check-in test
          </button>
        </div>
      </div>
    </li>
  );
}
