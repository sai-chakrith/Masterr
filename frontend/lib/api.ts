// Thin client for the FastAPI backend. Learning rules live only on the server.
import { accessToken, savedToken } from "./auth-client";
export type GapStatus = "unassessed" | "mastered" | "borderline" | "gap" | "resolved";

export interface Topic {
  skill_id: string;
  title: string;
  prerequisites: string[];
  status: GapStatus;
  source_session_id: string | null;
  scoring_version: "current" | "new";
  score: number | null;
  answer_count: number;
  mastery_bar: number;
  score_withheld: boolean;
  evidence_stale?: boolean;
}

export interface QuestionView {
  assignment_id: string;
  question_version_id: string;
  prompt: string;
  difficulty: string;
  position: number;
  facet: string;
  options?: { id: string; text: string }[];
}

export interface SessionView {
  session_id: string;
  skill_id: string;
  mode: string;
  status: string;
  policy_version: string;
  scoring_version: "current" | "new";
  stage: string | null;
  question_count: number;
  question: QuestionView | null;
  attempts: { attempt_id: string; answer: string; correct?: boolean; assistance: string }[];
}

export interface SubmitResult {
  saved: boolean;
  session_complete: boolean;
  correct?: boolean;
  result?: string;
  decision?: string;
  score?: number;
  answers?: number;
  explanation?: string;
  misconception_feedback?: {
    id: string;
    description: string;
    short_fix: string;
    occurrence_count: number;
    targeted_reset: boolean;
  };
  outcomes?: { attempt_id: string; correct: boolean; assistance: string }[];
}

export interface ReviewItem {
  assignment_id: string;
  prompt: string;
  answer: string;
  dont_know: boolean;
  solution: string;
}

export interface LearningAction {
  kind: string;
  skill_id: string | null;
  reason_code: string;
  reason: string;
}

export interface TeachingPlan {
  skill_id: string;
  curriculum_version: string;
  mode: "worked_examples" | "hinted_practice" | "practice_first";
  score: number | null;
  content_available: boolean;
  objective: string | null;
  lesson: string | null;
  worked_example: { prompt: string; steps: string[]; answer: string } | null;
  half_worked_example: { prompt: string; steps: string[]; learner_prompt: string } | null;
  hints_available: boolean;
  explanation_after_mistake: boolean;
}

export interface Roadmap {
  route_skill_ids: string[];
  state_fingerprint: string;
  nodes: {
    skill_id: string;
    title: string;
    prerequisites: string[];
    status: string;
    phase: string;
    score: number | null;
    mastery_bar: number;
    answer_count: number;
    next_review_at: string | null;
    available: boolean;
    evidence_stale?: boolean;
    source_session_id: string | null;
  }[];
  next_actions: LearningAction[];
  weekly_pace: { remaining_topics: number; weeks_left: number; topics_per_week: number | null; exam_date_passed: boolean } | null;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "mastrr-token";

export function getToken(): string | null {
  return savedToken();
}

export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new Event("mastrr-auth"));
  } catch {
    /* storage unavailable: the user signs in again next visit */
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token: string | null;
  try { token = await accessToken(); }
  catch { throw new ApiError(401, "session_expired", "Your session expired. Please sign in again."); }
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...init, headers, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const code = body?.error?.code ?? (response.status === 401 ? "unauthenticated" : "error");
    const detail = body?.error?.message ?? (typeof body?.detail === "string" ? body.detail : "Request failed.");
    throw new ApiError(response.status, code, detail);
  }
  return body as T;
}

export const api = {
  completeTutoring: (skill: string, id: string) => request<{ next: string }>(`/v1/me/tutor/${encodeURIComponent(skill)}/complete`, {
    method: "POST", body: JSON.stringify({ tutoring_id: id }),
  }),
  account: () => request<{ subject: string; content_reviewer: boolean; local_development: boolean;
    tutor_usage: { calls: number; daily_call_limit: number; period: string } }>("/v1/me/account"),
  exportData: () => request<Record<string, unknown>>("/v1/me/export"),
  deleteAccount: () => request<{ identity_deleted: boolean; message: string }>("/v1/me/account", {
    method: "DELETE", body: JSON.stringify({ confirmation: "DELETE" }),
  }),
  reportQuestion: (id: string, message: string) => request<{ id: string }>(`/v1/assignments/${id}/report`, {
    method: "POST", body: JSON.stringify({ message }),
  }),
  curriculum: () => request<{
    id: string;
    version: string;
    status: string;
    skills: { id: string; title: string; prerequisites: string[]; objective: string | null; lesson: string | null }[];
    exam_profiles: {
      id: string;
      name: string;
      target_skill_ids: string[];
      default_mastery_bar: number;
      topic_bars: Record<string, number>;
    }[];
  }>("/v1/curriculum"),
  goal: () => request<{
    target_skill_ids: string[];
    route_skill_ids: string[];
    exam_profile_id: string | null;
    exam_profile_version: string | null;
    exam_profile_name: string | null;
    exam_date: string | null;
    timezone: string;
  } | null>("/v1/me/goal"),
  setGoal: (body: { target_skill_ids?: string[]; exam_profile_id?: string | null; exam_date?: string | null; timezone?: string }) =>
    request<{ route_skill_ids: string[]; exam_profile_id: string | null; exam_profile_name: string | null }>("/v1/me/goal", {
      method: "PUT", body: JSON.stringify(body),
    }),
  roadmap: () => request<Roadmap>("/v1/me/roadmap"),
  teaching: (skillId: string) => request<TeachingPlan>(`/v1/me/teaching/${skillId}`),
  nextAction: () => request<{
    state_fingerprint: string;
    availability: string;
    actions: LearningAction[];
  }>("/v1/me/next-action"),
  logRecommendation: (state_fingerprint: string, action_index: number) =>
    request<{ recommendation_id: string; action: LearningAction }>("/v1/me/recommendations", {
      method: "POST", body: JSON.stringify({ state_fingerprint, action_index }),
    }),
  dismissRecommendation: (id: string) =>
    request<{ status: string }>("/v1/me/recommendations/" + id + "/dismiss", { method: "POST" }),
  followRecommendation: (id: string) =>
    request<{ status: string }>("/v1/me/recommendations/" + id + "/follow", { method: "POST" }),
  gaps: () => request<Topic[]>("/v1/me/gaps"),
  today: () => request<{
    active_session_id: string | null;
    reviews: { id: string; skill_id: string; is_due: boolean; due_at: string }[];
  }>("/v1/me/today"),
  session: (id: string) => request<SessionView>(`/v1/sessions/${id}`),
  startDiagnostic: (skill: string) =>
    request<{ session_id: string }>("/v1/sessions", {
      method: "POST",
      body: JSON.stringify({ skill_id: skill, mode: "diagnostic" }),
    }),
  startPractice: (skill: string) =>
    request<{ session_id: string }>("/v1/sessions", {
      method: "POST", body: JSON.stringify({ skill_id: skill, mode: "practice" }),
    }),
  startReview: (skill: string, reviewId: string) =>
    request<{ session_id: string }>("/v1/sessions", {
      method: "POST", body: JSON.stringify({ skill_id: skill, mode: "review", review_id: reviewId }),
    }),
  startRetest: (skill: string) => request<{ session_id: string }>(`/v1/topics/${skill}/retest`, { method: "POST" }),
  startValidation: (skill: string) =>
    request<{ session_id: string; stage: string }>(`/v1/topics/${skill}/validation`, { method: "POST" }),
  abandon: (id: string) => request<{ status: string }>(`/v1/sessions/${id}/abandon`, { method: "POST" }),
  borderlineReview: (id: string) =>
    request<{ items: ReviewItem[]; skill_id: string; next_action: string }>(`/v1/sessions/${id}/borderline-review`),
  submit: (
    assignmentId: string,
    key: string,
    body: { answer: string; option_id?: string | null; dont_know: boolean; working: string; duration_ms: number },
  ) =>
    request<SubmitResult>(`/v1/assignments/${assignmentId}/submit`, {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify(body),
    }),
  help: (assignmentId: string, kind: "hint" | "solution") =>
    request<{ kind: string; text: string; assessment_ended: boolean }>(
      `/v1/assignments/${assignmentId}/help`,
      { method: "POST", body: JSON.stringify({ kind }) },
    ),
};
