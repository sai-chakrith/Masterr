"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api, type ReviewItem } from "@/lib/api";

// D5 Borderline path: review missed and "I don't know" diagnostic questions, then retest.
export default function BorderlineReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [skill, setSkill] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .borderlineReview(id)
      .then((r) => {
        setItems(r.items);
        setSkill(r.skill_id);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(e instanceof ApiError ? e.message : "Could not load the review.");
      });
  }, [id, router]);

  async function retest() {
    if (!skill) return;
    setBusy(true);
    try {
      const created = await api.startRetest(skill);
      router.push(`/session/${created.session_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the retest.");
      setBusy(false);
    }
  }

  if (error) return <p className="text-rose-600">{error}</p>;
  if (!items) return <p className="text-slate-500">Loading...</p>;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold">Review before your retest</h1>
      <p className="text-sm text-slate-600 dark:text-slate-300">
        You are close to the bar. Read through the questions you missed, then take the 10-question retest. You need 7
        correct, and &quot;I don&apos;t know&quot; does not count as correct.
      </p>
      <ol className="space-y-4">
        {items.map((item, i) => (
          <li key={item.assignment_id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
            <p className="font-medium">
              {i + 1}. {item.prompt}
            </p>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Your answer: {item.dont_know ? "I don't know" : item.answer}
            </p>
            <p className="mt-2 text-sm leading-relaxed">{item.solution}</p>
          </li>
        ))}
      </ol>
      <div className="flex gap-3">
        <button
          onClick={retest}
          disabled={busy}
          className="rounded-md bg-slate-900 px-4 py-2 text-white dark:bg-slate-100 dark:text-slate-900"
        >
          Take the retest
        </button>
        <Link href="/" className="px-2 py-2 text-sm underline">
          Later
        </Link>
      </div>
    </div>
  );
}
