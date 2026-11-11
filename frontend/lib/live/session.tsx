"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError, errorText, RECRUITER_ROLES, STAFF_ROLES, type Organization, type Session } from "@/lib/api/phase3";

const ORG_KEY = "im-hire-organization";

type LiveValue = {
  session: Session;
  admin: boolean;
  /** Recruiter, admin or owner of the selected organization (or platform admin). */
  recruiter: boolean;
  organizations: Organization[];
  orgId: string;
  org: Organization | null;
  /** `/api/recruitment/organizations/<id>` for the selected organization. */
  orgPath: string;
  setOrgId: (id: string) => void;
  reloadOrganizations: () => Promise<void>;
  get: <T>(path: string) => Promise<T>;
  send: <T>(path: string, method: string, body?: unknown) => Promise<T>;
  upload: <T>(path: string, form: FormData) => Promise<T>;
  logout: () => Promise<void>;
};

const LiveContext = createContext<LiveValue | null>(null);

export function isStaff(session: Session) {
  return session.user.is_platform_admin || session.user.memberships.some((m) => STAFF_ROLES.includes(m.role));
}

export function homeFor(session: Session) {
  return isStaff(session) ? "/dashboard" : "/portal";
}

type State =
  | { status: "loading" }
  | { status: "offline"; message: string }
  | { status: "ready"; session: Session; organizations: Organization[]; orgId: string };

/**
 * Loads the signed-in session and organizations once, and guards an area:
 * "staff" pages send candidates to the portal; everyone signed out goes to /login.
 */
export function LiveProvider({ area, children }: { area: "staff" | "candidate"; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const session = await api<Session>("/api/auth/me");
        if (area === "staff" && !isStaff(session)) {
          router.replace("/portal");
          return;
        }
        const organizations = await api<Organization[]>("/api/recruitment/organizations");
        let stored = "";
        try {
          stored = window.localStorage.getItem(ORG_KEY) || "";
        } catch {
          /* storage unavailable */
        }
        const orgId = organizations.some((o) => o.id === stored) ? stored : organizations[0]?.id || "";
        if (alive) setState({ status: "ready", session, organizations, orgId });
      } catch (error) {
        if (!alive) return;
        if (error instanceof ApiError && error.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        } else {
          setState({ status: "offline", message: errorText(error) });
        }
      }
    })();
    return () => {
      alive = false;
    };
    // The path only matters for the sign-in return address.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area, router, attempt]);

  const ready = state.status === "ready" ? state : null;
  const csrf = ready?.session.csrf_token || "";

  const get = useCallback(<T,>(path: string) => api<T>(path), []);
  const send = useCallback(
    <T,>(path: string, method: string, body?: unknown) =>
      api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }, csrf),
    [csrf],
  );
  const upload = useCallback(<T,>(path: string, form: FormData) => api<T>(path, { method: "POST", body: form }, csrf), [csrf]);
  const setOrgId = useCallback((id: string) => {
    try {
      window.localStorage.setItem(ORG_KEY, id);
    } catch {
      /* storage unavailable */
    }
    setState((current) => (current.status === "ready" ? { ...current, orgId: id } : current));
  }, []);
  const reloadOrganizations = useCallback(async () => {
    const organizations = await api<Organization[]>("/api/recruitment/organizations");
    setState((current) =>
      current.status === "ready"
        ? { ...current, organizations, orgId: organizations.some((o) => o.id === current.orgId) ? current.orgId : organizations[0]?.id || "" }
        : current,
    );
  }, []);
  const logout = useCallback(async () => {
    await api("/api/auth/logout", { method: "POST", body: "{}" }, csrf);
    router.replace("/login");
  }, [csrf, router]);

  const value = useMemo<LiveValue | null>(() => {
    if (!ready) return null;
    const { session, organizations, orgId } = ready;
    const admin = session.user.is_platform_admin;
    const recruiter = admin || session.user.memberships.some((m) => m.organization_id === orgId && RECRUITER_ROLES.includes(m.role));
    return {
      session, admin, recruiter, organizations, orgId,
      org: organizations.find((o) => o.id === orgId) || null,
      orgPath: `/api/recruitment/organizations/${encodeURIComponent(orgId)}`,
      setOrgId, reloadOrganizations, get, send, upload, logout,
    };
  }, [ready, setOrgId, reloadOrganizations, get, send, upload, logout]);

  if (state.status === "offline") {
    return (
      <main className="gate">
        <div className="panel gate-card" role="alert">
          <h1 className="section-title">We could not load your workspace</h1>
          <p className="text-muted mt-2">{state.message}</p>
          <button className="btn btn-primary mt-4" onClick={() => { setState({ status: "loading" }); setAttempt((n) => n + 1); }}>
            Try again
          </button>
        </div>
      </main>
    );
  }
  if (!value) {
    return (
      <main className="gate" aria-busy="true">
        <div className="panel gate-card">
          <div className="skeleton" style={{ width: "60%" }} />
          <div className="skeleton mt-3" />
          <p className="text-muted mt-4">Checking your sign-in…</p>
        </div>
      </main>
    );
  }
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveValue {
  const value = useContext(LiveContext);
  if (!value) throw new Error("useLive must be used inside LiveProvider");
  return value;
}
