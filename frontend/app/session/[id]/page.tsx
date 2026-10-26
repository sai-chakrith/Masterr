"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type SessionView, type SubmitResult } from "@/lib/api";
import { DONT_KNOW_WORDING, resultText, sessionTitle } from "@/lib/labels";

function newKey() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [view, setView] = useState<SessionView | null>(null);
  const [answer, setAnswer] = useState("");
  const [selectedOptionId, setSelectedOptionId] = useState("");
  const [feedback, setFeedback] = useState<boolean | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [misconceptionFeedback, setMisconceptionFeedback] = useState<SubmitResult["misconception_feedback"]>();
  const [hint, setHint] = useState<string | null>(null);
  const [finished, setFinished] = useState<SubmitResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Browser timing (C3): from when the question is shown until the answer is sent.
  const shownAt = useRef<number>(0);
  // One idempotency key per question, reused if the network makes us retry.
  const keys = useRef<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const next = await api.session(id);
      setView(next);
      setAnswer("");
      setSelectedOptionId("");
      setHint(null);
      shownAt.current = performance.now();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e instanceof ApiError ? e.message : "Could not load this session.");
    }
  }, [id, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function send(dontKnow: boolean) {
    const question = view?.question;
    if (!question) return;
    setBusy(true);
    setError(null);
    keys.current[question.assignment_id] ??= newKey();
    try {
      const result = await api.submit(question.assignment_id, keys.current[question.assignment_id], {
        answer: dontKnow ? "" : answer.trim(),
        option_id: dontKnow ? null : (question.options?.length ? selectedOptionId : null),
        dont_know: dontKnow,
        working: "",
        duration_ms: Math.max(0, Math.round(performance.now() - shownAt.current)),
      });
      setFeedback(result.correct ?? null);
      setExplanation(result.explanation ?? null);
      setMisconceptionFeedback(result.misconception_feedback);
      if (result.session_complete) setFinished(result);
      else await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Your answer was not saved. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function abandon() {
    if (!view || !window.confirm("Leave this session? Its questions will not be offered again.")) return;
    await api.abandon(view.session_id).catch(() => undefined);
    router.push("/");
  }

  async function requestHint() {
    const assignmentId = view?.question?.assignment_id;
    if (!assignmentId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.help(assignmentId, "hint");
      setHint(result.text);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load a hint.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !view) return <p className="text-rose-600">{error}</p>;
  if (!view) return <p className="text-slate-500">Loading...</p>;

  const title = sessionTitle(view.policy_version, view.stage);
  const isDiagnosticV2 = view.policy_version === "mastery-diagnostic-v2";
  const allowDontKnow =
    !view.policy_version.startsWith("legacy-") &&
    (view.scoring_version === "new" || view.policy_version === "validation-form-v1");
  const position = view.question?.position ?? view.question_count;
  const total = isDiagnosticV2 ? `up to 12` : String(view.question_count);

  if (finished || view.status === "completed") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="rounded-lg bg-slate-50 p-4 dark:bg-slate-900">
          {resultText(finished?.result, finished?.decision)}
        </p>
        {finished?.outcomes && (
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {finished.outcomes.filter((o) => o.correct).length} of {finished.outcomes.length} correct.
          </p>
        )}
        {finished?.decision === "borderline" && (
          <Link href={`/review/${view.session_id}`} className="inline-block rounded-md bg-amber-400 px-4 py-2 font-medium text-slate-900">
            Review missed questions
          </Link>
        )}
        <div>
          <Link href="/" className="text-sky-700 underline dark:text-sky-300">
            Back to roadmap
          </Link>
        </div>
      </div>
    );
  }

  if (view.status === "abandoned") {
    return (
      <p>
        This session was left unfinished. <Link href="/" className="underline">Back to roadmap</Link>
      </p>
    );
  }

  const question = view.question;
  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <span className="text-sm text-slate-500 dark:text-slate-400" data-testid="progress">
          Question {position} of {total}
        </span>
      </div>
      {view.question_count >= 10 && !isDiagnosticV2 && (
        <ol className="flex gap-1" aria-label="Retest progress">
          {Array.from({ length: view.question_count }, (_, i) => (
            <li
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i < position - 1 ? "bg-sky-500" : i === position - 1 ? "bg-sky-300" : "bg-slate-200 dark:bg-slate-800"}`}
            />
          ))}
        </ol>
      )}
      {feedback !== null && (
        <p
          className={`text-sm ${feedback ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}`}
          aria-live="polite"
        >
          Previous answer: {feedback ? "correct" : "not correct"}
        </p>
      )}
      {misconceptionFeedback && (
        <aside className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100" aria-live="polite">
          <p className="font-semibold">{misconceptionFeedback.targeted_reset ? "Let's reset this idea" : "Check this idea"}</p>
          <p className="mt-1">{misconceptionFeedback.description}</p>
          {misconceptionFeedback.targeted_reset && <p className="mt-1">This same misconception has appeared more than once. Review the key step:</p>}
          <p className="mt-1">{misconceptionFeedback.short_fix}</p>
        </aside>
      )}
      {explanation && (
        <aside className="rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-100" aria-live="polite">
          <p className="font-semibold">Worked explanation</p>
          <p className="mt-1">{explanation}</p>
        </aside>
      )}
      {question && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(false);
          }}
          className="space-y-4"
        >
          <p className="text-lg leading-relaxed">{question.prompt}</p>
          {view.mode === "practice" && (
            <div className="space-y-2">
              <button type="button" onClick={() => void requestHint()} disabled={busy}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700">
                Get a hint
              </button>
              {hint && <p className="rounded-lg bg-sky-50 p-3 text-sm text-sky-950 dark:bg-sky-950 dark:text-sky-100" aria-live="polite">{hint}</p>}
            </div>
          )}
          {question.options?.length ? (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium">Choose one answer</legend>
              {question.options.map((option) => (
                <label key={option.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-300 p-3 dark:border-slate-700">
                  <input type="radio" name="answer-option" value={option.id} checked={selectedOptionId === option.id}
                    onChange={() => setSelectedOptionId(option.id)} />
                  <span>{option.text}</span>
                </label>
              ))}
            </fieldset>
          ) : (
            <input
              inputMode="numeric"
              autoFocus
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              aria-label="Your answer (a whole number)"
              placeholder="Whole number"
              className="w-48 rounded-md border border-slate-300 bg-transparent px-3 py-2 text-lg dark:border-slate-700"
            />
          )}
          <div className="flex flex-wrap items-start gap-3">
            <button
              type="submit"
              disabled={busy || (question.options?.length ? !selectedOptionId : !answer.trim())}
              className="rounded-md bg-slate-900 px-4 py-2 text-white dark:bg-slate-100 dark:text-slate-900"
            >
              Submit
            </button>
            {allowDontKnow && (
              <div className="max-w-xs">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => send(true)}
                  className="rounded-md border border-slate-300 px-4 py-2 dark:border-slate-700"
                >
                  I don&apos;t know
                </button>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{DONT_KNOW_WORDING}</p>
              </div>
            )}
          </div>
        </form>
      )}
      {error && <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      <button onClick={abandon} className="text-xs text-slate-500 underline dark:text-slate-400">
        Leave session
      </button>
    </div>
  );
}
