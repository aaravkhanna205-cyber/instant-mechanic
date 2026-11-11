/** Typed client for the FastAPI backend. Every call sends the session cookie. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type Membership = { organization_id: string; role: string };
export type Account = { id: string; email: string; full_name: string; is_platform_admin: boolean; memberships: Membership[] };
export type Session = { user: Account; csrf_token: string };
export type Organization = { id: string; name: string; slug: string };
export type Category = { slug: string; title: string; department: string };
export type Job = {
  id: string; organization_id: string; title: string; category_slug: string; description: string;
  location: string | null; employment_type?: string; status: string; created_at: string | null;
};
export type Application = {
  id: string; job_id: string; candidate_id: string; stage: string; applied_at: string | null;
  job_title?: string; job_location?: string | null; candidate_name?: string; candidate_email?: string;
};
export type StageChange = {
  id: string; previous_stage: string | null; new_stage: string; note: string | null;
  changed_by: string | null; changed_at: string | null;
};
export type Candidate = {
  id: string; full_name: string; email: string; phone?: string | null; city: string | null;
  skills: Record<string, unknown>;
};
export type CandidateProfile = { exists: boolean; phone: string | null; city: string | null; skills: Record<string, unknown> };
export type Interview = {
  id: string; application_id: string; status: string; scheduled_at: string | null; meeting_url?: string | null;
  job_title?: string; candidate_name?: string; feedback_count?: number;
};
export type Feedback = { id: string; reviewer_id: string; reviewer: string; score: number | null; comments: string | null };
export type Analytics = {
  jobs: number; applications: number; interviews: number; candidates: number;
  stages: Record<string, number>; job_statuses: Record<string, number>;
};
export type AdminUser = { id: string; email: string; full_name: string; active: boolean; is_platform_admin: boolean };
export type Member = { user_id: string; email: string; full_name: string; role: string; active: boolean };
export type ImportBatch = { id: string; filename: string; status: string; kind?: string; created_at: string };
export type RowError = { row: number; errors: string[] };
export type ImportPreview = {
  filename: string; valid_count: number; errors: RowError[]; sample: Record<string, unknown>[];
  new_accounts?: number; existing_accounts?: number;
};
export type AppSetting = { key: string; value: unknown };
export type AuditEntry = { action: string; actor_id: string | null; created_at: string | null; context: Record<string, unknown> };
export type DeletionRequest = {
  id: string; status: string; reason: string | null; created_at: string | null;
  decided_at: string | null; decision_note: string | null;
};
export type AdminDeletionRequest = DeletionRequest & { user_id: string; email: string; full_name: string };

export const STAGES = ["applied", "screening", "shortlisted", "trade_test", "interview", "offer", "hired", "rejected", "withdrawn"] as const;
export const JOB_STATUSES = ["draft", "published", "paused", "closed"] as const;
export const INTERVIEW_STATUSES = ["scheduled", "in_progress", "completed", "cancelled", "no_show"] as const;
export const STAFF_ROLES = ["owner", "admin", "recruiter", "interviewer"];
export const RECRUITER_ROLES = ["owner", "admin", "recruiter"];

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail: unknown = null) {
    super(message);
  }
}

function describe(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg}]
    return detail.map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : JSON.stringify(item))).join("; ");
  }
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  return fallback;
}

export async function api<T>(path: string, options: RequestInit = {}, csrf = ""): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: "include", cache: "no-store" });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the backend is running and allows this address.");
  }
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail ?? null;
    throw new ApiError(response.status, describe(detail, response.statusText || "Request failed"), detail);
  }
  return data as T;
}

export const encoded = (id: string) => encodeURIComponent(id);
export const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));
