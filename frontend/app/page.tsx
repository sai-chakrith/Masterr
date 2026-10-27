"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, getToken, type LearningAction, type Roadmap } from "@/lib/api";
import SkillRouteGraph from "@/components/SkillRouteGraph";

function labelStatus(status: string) {
  return status === "unassessed" ? "Not checked yet" : status[0].toUpperCase() + status.slice(1);
}

function statusClasses(status: string) {
  if (status === "mastered" || status === "resolved") return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
  if (status === "gap") return "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200";
  if (status === "borderline") return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
  return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200";
}

export default function RoadmapPage() {
  const router = useRouter();
  const [curriculum, setCurriculum] = useState<Awaited<ReturnType<typeof api.curriculum>> | null>(null);
  const [goal, setGoal] = useState<Awaited<ReturnType<typeof api.goal>>>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [targets, setTargets] = useState<string[]>([]);
  const [examProfileId, setExamProfileId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const generation = useRef(0);
  const hydrated = useRef(false);
  const load = useCallback(async () => {
    const request = ++generation.current;
    try {
      const [catalog, savedGoal, today] = await Promise.all([api.curriculum(), api.goal(), api.today()]);
      if (request !== generation.current) return;
      setCurriculum(catalog);
      setGoal(savedGoal);
      setActive(today.active_session_id);
      if (savedGoal) {
        const [route, suggestion] = await Promise.all([api.roadmap(), api.nextAction()]);
        if (request !== generation.current) return;
        setRoadmap({ ...route, next_actions: suggestion.actions, state_fingerprint: suggestion.state_fingerprint });
        if (!hydrated.current) {
          setTargets(savedGoal.target_skill_ids);
          setDate(savedGoal.exam_date ?? "");
          setExamProfileId(savedGoal.exam_profile_id ?? "");
        }
      }
      hydrated.current = true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e instanceof ApiError ? e.message : "The backend is not reachable. Start it with scripts/start-local.ps1.");
    }
  }, [router]);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else void load();
    return () => { generation.current++; };
  }, [load, router]);

  async function saveGoal(event: FormEvent) {
    event.preventDefault();
    if (!targets.length && !examProfileId) return;
    generation.current++;
    setBusy(true); setError(null); setNotice(null);
    try {
      await api.setGoal({ target_skill_ids: targets, exam_profile_id: examProfileId || null,
        exam_date: date || null, timezone: "Asia/Kolkata" });
      setDismissed(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the goal.");
    } finally { setBusy(false); }
  }

  async function startAction(index: number, action?: LearningAction) {
    if (!roadmap || !action) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const logged = await api.logRecommendation(roadmap.state_fingerprint, index);
      if (action.kind === "resume_timed_test") {
        await api.followRecommendation(logged.recommendation_id);
        router.push("/practice-test"); return;
      }
      if (action.kind === "resume" && active) {
        await api.followRecommendation(logged.recommendation_id);
        router.push("/session/" + active); return;
      }
      if (action.kind === "diagnostic") {
        if (!action.skill_id) return;
        const created = await api.startDiagnostic(action.skill_id);
        await api.followRecommendation(logged.recommendation_id);
        router.push("/session/" + created.session_id); return;
      }
      if (action.kind === "tutoring" && action.skill_id) {
        await api.followRecommendation(logged.recommendation_id);
        router.push("/tutor?topic=" + encodeURIComponent(action.skill_id)); return;
      }
      if ((action.kind === "prerequisite_check" || action.kind === "alternate_teaching") && action.skill_id) {
        await api.followRecommendation(logged.recommendation_id);
        router.push("/learn/" + action.skill_id); return;
      }
      if (action.kind === "retest" || action.kind === "practice") {
        if (!action.skill_id) return;
        const created = action.kind === "retest"
          ? await api.startRetest(action.skill_id)
          : await api.startPractice(action.skill_id);
        await api.followRecommendation(logged.recommendation_id);
        router.push("/session/" + created.session_id); return;
      }
      if (action.kind === "review" && action.skill_id) {
        const today = await api.today();
        const due = today.reviews.find((item) => item.skill_id === action.skill_id && item.is_due);
        if (!due) throw new Error("That review is no longer due. Refresh your suggestions.");
        const created = await api.startReview(action.skill_id, due.id);
        await api.followRecommendation(logged.recommendation_id);
        router.push("/session/" + created.session_id); return;
      }
      if (action.kind === "mistake_review" && action.skill_id) {
        const node = roadmap.nodes.find((item) => item.skill_id === action.skill_id);
        if (node?.source_session_id) {
          await api.followRecommendation(logged.recommendation_id);
          router.push("/review/" + node.source_session_id); return;
        }
      }
      if (action.kind === "route_complete") {
        await api.followRecommendation(logged.recommendation_id);
        setNotice("This route is complete. Choose another target above or keep your current goal for reviews.");
        return;
      }
      await api.dismissRecommendation(logged.recommendation_id);
      setNotice("That activity is not ready yet. It needs reviewed teaching or question content.");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Could not start that activity.");
    } finally { setBusy(false); }
  }

  async function dismissPrimary() {
    if (!roadmap || !roadmap.next_actions[0]) return;
    setBusy(true); setError(null);
    try {
      const logged = await api.logRecommendation(roadmap.state_fingerprint, 0);
      await api.dismissRecommendation(logged.recommendation_id);
      setDismissed(true);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not dismiss this suggestion."); }
    finally { setBusy(false); }
  }

  if (!curriculum) return <p className="text-slate-500">{error ?? "Loading Mastrr..."}</p>;

  const actions = dismissed ? roadmap?.next_actions.slice(1) ?? [] : roadmap?.next_actions ?? [];
  const primary = dismissed ? undefined : actions[0];
  const profileStatus = curriculum.exam_profiles.length
    ? "Choose a reviewed exam profile, then add any extra target topics."
    : "Exam profiles are still being mapped and reviewed; choose target topics for now.";

  return (
    <div className="space-y-7">
      <header>
        <p className="text-sm font-medium text-sky-700 dark:text-sky-300">Your study route</p>
        <h1 className="mt-1 text-3xl font-semibold">Numbers, one next step at a time</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-300">
          Prerequisites help order the route. They never prevent you from choosing another topic.
        </p>
      </header>

      {active && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-900 dark:bg-sky-950">
          <span>You have an activity in progress.</span>
          <Link className="font-medium underline" href={"/session/" + active}>Resume activity</Link>
        </div>
      )}
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800 dark:bg-rose-950 dark:text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">{notice}</p>}
      {roadmap?.nodes.some((node) => node.evidence_stale) && <p role="status" className="rounded-lg border border-amber-300 p-3 text-sm">Some assessed content changed or was withdrawn. Previous results remain in your history; affected topics need a fresh independent check.</p>}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-lg font-semibold">Your goal</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{profileStatus}</p>
        {goal?.exam_profile_name && <p className="mt-2 text-sm font-medium">Profile: {goal.exam_profile_name}</p>}
        <form onSubmit={saveGoal} className="mt-4 space-y-4">
          <label className="grid max-w-xl gap-1 text-sm">
            <span>Exam profile (optional)</span>
            <select value={examProfileId} onChange={(event) => setExamProfileId(event.target.value)}
              disabled={!curriculum.exam_profiles.length}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950">
              <option value="">Choose topics directly</option>
              {curriculum.exam_profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
            </select>
          </label>
          {examProfileId && (() => {
            const profile = curriculum.exam_profiles.find((item) => item.id === examProfileId);
            return profile ? <p className="text-xs text-slate-600 dark:text-slate-300">
              Includes {profile.target_skill_ids.map((id) => curriculum.skills.find((skill) => skill.id === id)?.title ?? id).join(", ")}.
              Default target: {Math.round(profile.default_mastery_bar * 100)}%.
            </p> : null;
          })()}
          <fieldset>
            <legend className="text-sm font-medium">{examProfileId ? "Add extra target topics (optional)" : "Target topics (choose one or more)"}</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {curriculum.skills.map((skill) => <label key={skill.id} className="flex items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-700">
                <input type="checkbox" checked={targets.includes(skill.id)}
                  onChange={(event) => setTargets((current) => event.target.checked
                    ? [...current, skill.id] : current.filter((id) => id !== skill.id))} />
                <span>{skill.title}</span>
              </label>)}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            <span>Exam date (optional)</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-950" />
          </label>
          <button disabled={busy || (!targets.length && !examProfileId)} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-sky-300 dark:text-slate-950">
            {goal ? "Update goal" : "Set goal"}
          </button>
          </div>
        </form>
        {curriculum.status !== "approved" && (
          <p className="mt-3 text-xs text-amber-800 dark:text-amber-200">
            The curriculum is still a draft. Learner activities appear only after reviewed content is published.
          </p>
        )}
      </section>

      {goal && roadmap && (
        <>
          <section aria-labelledby="next-step-title" className="rounded-2xl border border-sky-200 bg-sky-50 p-5 dark:border-sky-900 dark:bg-sky-950">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-800 dark:text-sky-200">Recommended next step</p>
                {primary ? <>
                  <h2 id="next-step-title" className="mt-2 text-xl font-semibold">{primary.kind.replaceAll("_", " ")}</h2>
                  <p className="mt-1 max-w-2xl text-sm">{primary.reason}</p>
                </> : <p className="mt-2 text-sm">There is no activity available on this route yet. The question bank is still awaiting human review.</p>}
              </div>
              {primary && <div className="flex gap-2">
                <button disabled={busy} onClick={() => void startAction(0, primary)}
                  className="rounded-lg bg-sky-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 dark:bg-sky-300 dark:text-slate-950">Start</button>
                <button disabled={busy} onClick={() => void dismissPrimary()}
                  className="rounded-lg border border-sky-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-sky-700">Dismiss</button>
              </div>}
            </div>
            {actions.slice(1, 3).length > 0 && <div className="mt-4 flex flex-wrap gap-2">
              {actions.slice(1, 3).map((action, index) => (
                <button key={action.kind + action.skill_id} disabled={busy}
                  onClick={() => void startAction(index + 1, action)}
                  className="rounded-lg border border-sky-300 px-3 py-2 text-left text-sm hover:bg-white disabled:opacity-50 dark:border-sky-800 dark:hover:bg-slate-900">
                  <span className="block font-medium">{action.kind.replaceAll("_", " ")}</span>
                  <span className="block text-xs opacity-80">{action.reason}</span>
                </button>
              ))}
            </div>}
          </section>

          <section>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl font-semibold">Your route</h2>
              {roadmap.weekly_pace && <p className="text-sm text-slate-600 dark:text-slate-300">
                {roadmap.weekly_pace.exam_date_passed
                  ? "Your exam date has passed; update your goal to see a current pace."
                  : `About ${roadmap.weekly_pace.topics_per_week} route topic${roadmap.weekly_pace.topics_per_week === 1 ? "" : "s"} per week to cover what remains.`}
              </p>}
            </div>
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">Lines show prerequisite relationships. Select any topic to open its teaching page.</p>
            <div className="mt-3"><SkillRouteGraph nodes={roadmap.nodes} /></div>
            <ul className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600 dark:text-slate-300" aria-label="Topic status legend">
              {["mastered", "resolved", "borderline", "gap", "unassessed"].map((status) => (
                <li key={status} className="flex items-center gap-1.5">
                  <span className={`inline-block h-3 w-3 rounded-sm ${statusClasses(status)}`} aria-hidden="true" />
                  {labelStatus(status)}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
