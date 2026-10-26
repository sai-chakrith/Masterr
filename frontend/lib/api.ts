// Thin client for the FastAPI backend. Learning rules live only on the server.
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
}

export interface QuestionView {
  assignment_id: string;
  question_version_id: string;
  prompt: string;
  difficulty: string;
  position: number;
  facet: string;
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
  outcomes?: { attempt_id: string; correct: boolean; assistance: string }[];
}

export interface ReviewItem {
  assignment_id: string;
  prompt: string;
  answer: string;
  dont_know: boolean;
  solution: string;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "mastrr-token";

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the user signs in again next visit */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
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
  gaps: () => request<Topic[]>("/v1/me/gaps"),
  today: () => request<{ active_session_id: string | null }>("/v1/me/today"),
  session: (id: string) => request<SessionView>(`/v1/sessions/${id}`),
  startDiagnostic: (skill: string) =>
    request<{ session_id: string }>("/v1/sessions", {
      method: "POST",
      body: JSON.stringify({ skill_id: skill, mode: "diagnostic" }),
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
    body: { answer: string; dont_know: boolean; working: string; duration_ms: number },
  ) =>
    request<SubmitResult>(`/v1/assignments/${assignmentId}/submit`, {
      method: "POST",
      headers: { "Idempotency-Key": key },
      body: JSON.stringify(body),
    }),
};
