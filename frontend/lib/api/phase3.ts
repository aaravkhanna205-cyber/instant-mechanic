/** Typed client for the FastAPI backend. Every call sends the session cookie. */
// "same-origin" means the API is served from the same address as this site (behind a proxy).
const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;
export const API_URL = configuredApiUrl === "same-origin" ? "" : (configuredApiUrl || "http://127.0.0.1:8000");

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
/** Same groups as backend/app/security/roles.py. The server enforces them; these only shape the screens. */
export const FULL_ACCESS_ROLES = ["owner", "admin", "hr_manager", "hiring_manager"];
export const RECRUITER_ROLES = [...FULL_ACCESS_ROLES, "recruiter"];
export const STAFF_ROLES = [...RECRUITER_ROLES, "interviewer"];
export const TEAM_ROLES = STAFF_ROLES;
export const ROLE_LABELS: Record<string, string> = {
  owner: "Owner", admin: "Organization admin", hr_manager: "HR manager", hiring_manager: "Hiring manager",
  recruiter: "Recruiter", interviewer: "Interviewer", candidate: "Candidate",
};

// ---------- Phase 7 ----------
export type AppNotification = {
  id: string; kind: string; message: string; link: string | null; organization_id: string | null;
  read: boolean; email_status: string | null; created_at: string | null;
};
export type EmailLog = AppNotification & { to_name: string; to_email: string; emailed_at: string | null; email_error: string | null };
export type RoleInfo = { role: string; label: string; description: string; full_access: boolean; team_role: boolean };
export type TeamMember = {
  user_id: string; email: string; full_name: string; role: string; active: boolean; is_platform_admin: boolean; full_access: boolean;
};
export type SearchRow = {
  id: string; stage: string; applied_at: string | null; job_id: string; job_title: string;
  candidate_name: string; candidate_email: string; phone: string | null; city: string | null;
};
export type SearchPage = { items: SearchRow[]; total: number; page: number; page_size: number; pages: number };
export type ReportSummary = {
  days: number; from: string; to: string; applications: number; open_jobs: number; by_stage: Record<string, number>;
  funnel: { stage: string; count: number }[];
  conversion: { applied_to_interview: number | null; interview_to_offer: number | null; offer_to_hired: number | null };
  time_to_hire: { hires: number; average_days: number | null; median_days: number | null };
  interviews: { due: number; completed: number; by_status: Record<string, number>; completion_rate: number | null };
  jobs: { job_id: string; title: string; status: string; applications: number; interviewed: number; offers: number; hired: number }[];
  activity: { name: string; stage_changes: number }[];
};
export type Health = Record<string, boolean | number | string | null>;
export type RetentionPreview = {
  days: number; count: number;
  candidates: { user_id: string; full_name: string; email: string; applications: number; last_activity: string | null }[];
};

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

/** Downloads a file (for example a CSV export) using the signed-in session. */
export async function download(path: string, fallbackName: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { credentials: "include", cache: "no-store" });
  } catch {
    throw new ApiError(0, "Cannot reach the server.");
  }
  if (!response.ok) {
    let detail: unknown = null;
    try { detail = (await response.json())?.detail; } catch { /* not JSON */ }
    throw new ApiError(response.status, describe(detail, response.statusText || "Download failed"), detail);
  }
  const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") || "")?.[1] || fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));
