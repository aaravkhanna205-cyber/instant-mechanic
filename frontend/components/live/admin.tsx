"use client";
import { useCallback, useState } from "react";
import {
  encoded, ROLE_LABELS, type AdminDeletionRequest, type AdminUser, type AppSetting, type AuditEntry, type Health, type Member,
  type RetentionPreview,
} from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { ImportWorkspace } from "./imports";
import { ActionMessages, EmptyState, Field, formatDate, formatDateTime, LoadingRows, Notice, PageHeader, Pill } from "./ui";

const TABS = ["People and roles", "Organizations", "Data import", "Deletion requests", "Data retention", "System health", "Settings", "Audit log"] as const;
type Tab = (typeof TABS)[number];
const ROLES = ["hr_manager", "hiring_manager", "recruiter", "interviewer", "admin", "owner", "candidate"];

export function AdminPage() {
  const live = useLive();
  const [tab, setTab] = useState<Tab>("People and roles");
  const header = <PageHeader title="Super Admin" subtitle="People, organizations, imports, privacy requests and settings for the whole tool." />;
  if (!live.admin) {
    return <>{header}<EmptyState title="Platform administrator only" text="Ask a platform administrator if you need something changed here." /></>;
  }
  return (
    <div>
      {header}
      <div className="tabs" role="tablist" aria-label="Super Admin sections">
        {TABS.map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} className="tab" onClick={() => setTab(name)}>{name}</button>
        ))}
      </div>
      {tab === "People and roles" && <PeopleTab />}
      {tab === "Organizations" && <OrganizationsTab />}
      {tab === "Data import" && <ImportTab />}
      {tab === "Deletion requests" && <DeletionTab />}
      {tab === "Data retention" && <RetentionTab />}
      {tab === "System health" && <HealthTab />}
      {tab === "Settings" && <SettingsTab />}
      {tab === "Audit log" && <AuditTab />}
    </div>
  );
}

function PeopleTab() {
  const live = useLive();
  const action = useAction();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("recruiter");
  const [query, setQuery] = useState("");
  const loader = useCallback(async () => {
    const [users, members] = await Promise.all([
      live.get<AdminUser[]>("/api/admin-v3/users?limit=200"),
      live.orgId ? live.get<Member[]>(`/api/admin-v3/organizations/${encoded(live.orgId)}/members`) : Promise.resolve([]),
    ]);
    return { users, members };
  }, [live]);
  const source = useLoad(loader);

  const assign = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send("/api/admin-v3/memberships", "POST", { email: email.trim(), organization_id: live.orgId, role });
      setEmail("");
      source.reload();
    }, "Role saved.");
  };
  const remove = (member: Member) =>
    action.run(async () => {
      await live.send(`/api/admin-v3/organizations/${encoded(live.orgId)}/members/${encoded(member.user_id)}`, "DELETE");
      source.reload();
    }, `${member.full_name} was removed from ${live.org?.name}.`);
  const setSuper = (user: AdminUser, value: boolean) =>
    action.run(async () => {
      await live.send(`/api/phase7/admin/users/${encoded(user.id)}/platform-admin`, "POST", { value });
      source.reload();
    }, value ? `${user.full_name} is now a Super Admin.` : `${user.full_name} is no longer a Super Admin.`);
  const setActive = (user: AdminUser, active: boolean) =>
    action.run(async () => {
      await live.send(`/api/admin-v3/users/${encoded(user.id)}`, "PATCH", { active });
      source.reload();
    }, `${user.full_name} is now ${active ? "active" : "deactivated"}.`);

  if (!source.data) return source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />;
  const text = query.trim().toLowerCase();
  const users = source.data.users.filter((user) => !text || `${user.full_name} ${user.email}`.toLowerCase().includes(text));

  return (
    <div className="stack">
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      <section className="panel p-5 stack">
        <div>
          <h2 className="section-title">Roles in {live.org?.name || "this organization"}</h2>
          <p className="text-muted text-sm mt-1">The person must have registered first. HR managers, hiring managers, admins and owners have full access to the organization; recruiters handle jobs, candidates and interviews.</p>
        </div>
        {live.orgId ? (
          <form className="flex flex-wrap gap-2 items-end" onSubmit={assign}>
            <Field label="Registered email">
              <input type="email" className="control" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </Field>
            <Field label="Role">
              <select className="control" value={role} onChange={(event) => setRole(event.target.value)}>
                {ROLES.map((value) => <option key={value} value={value}>{ROLE_LABELS[value]}</option>)}
              </select>
            </Field>
            <button className="btn btn-primary" disabled={action.busy}>Assign role</button>
          </form>
        ) : <Notice>Create an organization first, in the Organizations tab.</Notice>}
        {source.data.members.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Member</th><th>Role</th><th>Action</th></tr></thead>
              <tbody>
                {source.data.members.map((member) => (
                  <tr key={member.user_id}>
                    <td>{member.full_name}<div className="text-muted text-xs">{member.email}</div></td>
                    <td><Pill value={ROLE_LABELS[member.role] || member.role} tone={["owner", "admin", "hr_manager", "hiring_manager"].includes(member.role) ? "orange" : undefined} /></td>
                    <td><button className="btn" disabled={action.busy} onClick={() => remove(member)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel p-5 stack">
        <h2 className="section-title">All accounts</h2>
        <div className="toolbar !mb-0">
          <input aria-label="Search accounts" className="control" placeholder="Search name or email" value={query}
            onChange={(event) => setQuery(event.target.value)} />
          <span className="text-muted text-sm">{users.length} shown (latest 200)</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Account</th><th>Type</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.full_name}<div className="text-muted text-xs">{user.email}</div></td>
                  <td>{user.is_platform_admin ? <Pill value="Super Admin" tone="orange" /> : "Standard"}</td>
                  <td><Pill value={user.active ? "active" : "deactivated"} tone={user.active ? "green" : "grey"} /></td>
                  <td>
                    {user.id === live.session.user.id ? <span className="text-muted">You</span> : (
                      <span className="flex flex-wrap gap-2">
                        <button className="btn" disabled={action.busy} onClick={() => setActive(user, !user.active)}>
                          {user.active ? "Deactivate" : "Reactivate"}
                        </button>
                        {user.active && (
                          <button className="btn" disabled={action.busy} onClick={() => setSuper(user, !user.is_platform_admin)}>
                            {user.is_platform_admin ? "Remove Super Admin" : "Make Super Admin"}
                          </button>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function slugify(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function OrganizationsTab() {
  const live = useLive();
  const action = useAction();
  const [name, setName] = useState(live.organizations.length ? "" : "Instant Mechanic");
  const [slug, setSlug] = useState(live.organizations.length ? "" : "instant-mechanic");
  const [touched, setTouched] = useState(false);
  const create = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send("/api/recruitment/organizations", "POST", { name: name.trim(), slug });
      await live.reloadOrganizations();
      setName("");
      setSlug("");
      setTouched(false);
    }, "Organization created.");
  };
  return (
    <div className="stack">
      <ActionMessages error={action.error} notice={action.notice} />
      <section className="panel p-5 stack">
        <h2 className="section-title">Organizations</h2>
        {live.organizations.length === 0 ? <p className="text-muted">None yet. Create Instant Mechanic below to begin.</p> : (
          <div className="rows">
            {live.organizations.map((org) => (
              <div key={org.id}>
                <span><strong>{org.name}</strong><span className="block text-muted text-xs">{org.slug}</span></span>
                {org.id === live.orgId ? <Pill value="selected" tone="amber" /> : <button className="btn" onClick={() => live.setOrgId(org.id)}>Switch to this</button>}
              </div>
            ))}
          </div>
        )}
      </section>
      <form className="panel p-5 stack max-w-2xl" onSubmit={create}>
        <h2 className="section-title">Add an organization</h2>
        <div className="form-grid">
          <Field label="Name">
            <input className="control" required minLength={2} maxLength={160} value={name}
              onChange={(event) => { setName(event.target.value); if (!touched) setSlug(slugify(event.target.value)); }} />
          </Field>
          <Field label="Short name" hint="Lower-case letters, numbers and hyphens.">
            <input className="control" required minLength={2} maxLength={120} pattern="[a-z0-9]+(-[a-z0-9]+)*" value={slug}
              onChange={(event) => { setSlug(event.target.value); setTouched(true); }} />
          </Field>
        </div>
        <div><button className="btn btn-primary" disabled={action.busy}>Create organization</button></div>
      </form>
    </div>
  );
}

function ImportTab() {
  const live = useLive();
  const [kind, setKind] = useState<"jobs" | "candidates">("jobs");
  if (!live.orgId) return <Notice>Create an organization first, in the Organizations tab.</Notice>;
  return (
    <div className="stack">
      <div className="flex flex-wrap gap-2" role="group" aria-label="What to import">
        <button className={`btn ${kind === "jobs" ? "btn-primary" : ""}`} aria-pressed={kind === "jobs"} onClick={() => setKind("jobs")}>Jobs</button>
        <button className={`btn ${kind === "candidates" ? "btn-primary" : ""}`} aria-pressed={kind === "candidates"} onClick={() => setKind("candidates")}>Candidates</button>
      </div>
      <ImportWorkspace key={kind} kind={kind} />
    </div>
  );
}

function DeletionTab() {
  const live = useLive();
  const action = useAction();
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState("");
  const loader = useCallback(() => live.get<AdminDeletionRequest[]>("/api/admin-v3/deletion-requests"), [live]);
  const requests = useLoad(loader);
  const decide = (request: AdminDeletionRequest, decision: "approve" | "reject") =>
    action.run(async () => {
      await live.send(`/api/admin-v3/deletion-requests/${encoded(request.id)}/decision`, "POST",
        { decision, note: (notes[request.id] || "").trim() || null });
      setConfirming("");
      requests.reload();
    }, decision === "approve" ? "Data deleted and account closed." : "Request rejected. Nothing was deleted.");

  if (!requests.data) return requests.error ? <Notice kind="error">{requests.error}</Notice> : <LoadingRows />;
  const pending = requests.data.filter((item) => item.status === "pending");
  const decided = requests.data.filter((item) => item.status !== "pending");

  return (
    <div className="stack">
      <Notice>
        Approving permanently deletes the person&apos;s profile, applications and interviews, and closes their account. It cannot be undone.
        Have your consent and retention wording checked by a lawyer before relying on this workflow.
      </Notice>
      <ActionMessages error={action.error || requests.error} notice={action.notice} />
      {pending.length === 0 ? <EmptyState title="No requests waiting" text="New deletion requests from candidates appear here." /> : pending.map((request) => (
        <section key={request.id} className="panel p-5 stack">
          <div className="flex flex-wrap justify-between gap-3">
            <div><strong>{request.full_name}</strong><div className="text-muted text-xs">{request.email} · asked {formatDateTime(request.created_at)}</div></div>
            <Pill value="pending" />
          </div>
          <p>{request.reason || <span className="text-muted">No reason given.</span>}</p>
          <Field label="Note for the record (optional)">
            <input className="control" maxLength={1000} value={notes[request.id] || ""}
              onChange={(event) => setNotes((current) => ({ ...current, [request.id]: event.target.value }))} />
          </Field>
          {confirming === request.id ? (
            <div className="notice notice-error" role="alert">
              <div className="stack">
                <span>Delete all recruitment data for {request.full_name}? This cannot be undone.</span>
                <div className="flex flex-wrap gap-2">
                  <button className="btn btn-primary" disabled={action.busy} onClick={() => decide(request, "approve")}>Yes, delete their data</button>
                  <button className="btn" disabled={action.busy} onClick={() => setConfirming("")}>Cancel</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" disabled={action.busy} onClick={() => setConfirming(request.id)}>Approve and delete</button>
              <button className="btn" disabled={action.busy} onClick={() => decide(request, "reject")}>Reject</button>
            </div>
          )}
        </section>
      ))}
      {decided.length > 0 && (
        <section className="panel p-5">
          <h2 className="section-title mb-3">Decided</h2>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Account</th><th>Outcome</th><th>Decided</th><th>Note</th></tr></thead>
              <tbody>
                {decided.map((request) => (
                  <tr key={request.id}>
                    <td>{request.full_name}</td>
                    <td><Pill value={request.status} tone={request.status === "completed" ? "green" : "grey"} /></td>
                    <td>{formatDateTime(request.decided_at)}</td>
                    <td className="wrap">{request.decision_note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function SettingsTab() {
  const live = useLive();
  const action = useAction();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const loader = useCallback(() => live.get<AppSetting[]>("/api/admin-v3/settings"), [live]);
  const settings = useLoad(loader);
  const save = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send(`/api/admin-v3/settings/${encoded(key.trim())}`, "PUT", { value });
      setKey("");
      setValue("");
      settings.reload();
    }, "Setting saved.");
  };
  return (
    <div className="stack">
      <ActionMessages error={action.error || settings.error} notice={action.notice} />
      <form className="panel p-5 stack max-w-2xl" onSubmit={save}>
        <div>
          <h2 className="section-title">Application settings</h2>
          <p className="text-muted text-sm mt-1">Simple named values, such as a notice for recruiters. Passwords, keys and tokens are refused here.</p>
        </div>
        <div className="form-grid">
          <Field label="Name" hint="Lower-case letters, numbers and underscores, e.g. recruitment_notice">
            <input className="control" required pattern="[a-z][a-z0-9_]{1,79}" value={key} onChange={(event) => setKey(event.target.value)} />
          </Field>
          <Field label="Value">
            <input className="control" value={value} onChange={(event) => setValue(event.target.value)} />
          </Field>
        </div>
        <div><button className="btn btn-primary" disabled={action.busy}>Save setting</button></div>
      </form>
      <section className="panel p-5">
        <h2 className="section-title mb-3">Saved settings</h2>
        {!settings.data ? <p className="text-muted">Loading…</p> : settings.data.length === 0 ? <p className="text-muted">None saved yet.</p> : (
          <div className="rows">
            {settings.data.map((item) => (
              <div key={item.key}>
                <span><strong>{item.key}</strong><span className="block text-muted break-all">{typeof item.value === "string" ? item.value : JSON.stringify(item.value)}</span></span>
                <button className="btn" onClick={() => { setKey(item.key); setValue(typeof item.value === "string" ? item.value : JSON.stringify(item.value)); }}>Edit</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function AuditTab() {
  const live = useLive();
  const [query, setQuery] = useState("");
  const loader = useCallback(() => live.get<AuditEntry[]>("/api/admin-v3/audit"), [live]);
  const audit = useLoad(loader);
  if (!audit.data) return audit.error ? <Notice kind="error">{audit.error}</Notice> : <LoadingRows />;
  const text = query.trim().toLowerCase();
  const shown = audit.data.filter((entry) => !text || entry.action.toLowerCase().includes(text));
  return (
    <section className="panel p-5 stack">
      <div className="toolbar !mb-0">
        <input aria-label="Filter audit log" className="control" placeholder="Filter by action, e.g. job" value={query}
          onChange={(event) => setQuery(event.target.value)} />
        <button className="btn" onClick={audit.reload}>Refresh</button>
        <span className="text-muted text-sm">Latest 100 actions</span>
      </div>
      {shown.length === 0 ? <p className="text-muted">Nothing recorded.</p> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>When</th><th>Action</th><th>Details</th></tr></thead>
            <tbody>
              {shown.map((entry, index) => (
                <tr key={index}>
                  <td>{formatDateTime(entry.created_at)}</td>
                  <td>{entry.action}</td>
                  <td className="wrap text-muted">{Object.keys(entry.context || {}).length ? JSON.stringify(entry.context) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const HEALTH_LABELS: [string, string, "good-if-true" | "good-if-zero" | "count"][] = [
  ["database", "Database", "good-if-true"],
  ["redis", "Redis (sessions and queues)", "good-if-true"],
  ["worker_running_now", "Agent and email worker busy right now", "count"],
  ["users", "Active accounts", "count"],
  ["organizations", "Organizations", "count"],
  ["emails_waiting", "Emails waiting to send", "count"],
  ["emails_failed", "Emails that failed", "good-if-zero"],
  ["resumes_waiting", "Resumes waiting to be read", "count"],
  ["resumes_failed", "Resumes that could not be read", "good-if-zero"],
  ["agent_messages_queued", "Agent messages queued", "count"],
  ["workflows_failed", "Agent workflows that failed", "good-if-zero"],
  ["deletion_requests_pending", "Deletion requests waiting", "good-if-zero"],
];

function HealthTab() {
  const live = useLive();
  const loader = useCallback(() => live.get<Health>("/api/phase7/admin/health"), [live]);
  const source = useLoad(loader);
  if (!source.data) return source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />;
  const data = source.data;
  return (
    <div className="stack">
      <div className="flex justify-between items-center gap-3">
        <p className="text-muted text-sm">Checked {formatDateTime(String(data.checked_at))}.</p>
        <button className="btn" onClick={source.reload}>Check again</button>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <tbody>
            {HEALTH_LABELS.map(([key, text, kind]) => {
              const value = data[key];
              const shown = value === null || value === undefined ? "Not available" : typeof value === "boolean" ? (value ? "Yes" : "No") : String(value);
              const bad = (kind === "good-if-true" && value === false) || (kind === "good-if-zero" && typeof value === "number" && value > 0);
              return (
                <tr key={key}>
                  <td>{text}</td>
                  <td>{kind === "count" ? <strong>{shown}</strong> : <Pill value={shown} tone={bad ? "red" : "green"} />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-muted text-xs">&ldquo;Worker busy right now&rdquo; is only Yes for the few seconds the worker is processing; No is normal.</p>
    </div>
  );
}

function RetentionTab() {
  const live = useLive();
  const action = useAction();
  const [days, setDays] = useState(365);
  const [typed, setTyped] = useState("");
  const loader = useCallback(() => live.get<RetentionPreview>(`/api/phase7/admin/retention?days=${days}`), [live, days]);
  const source = useLoad(loader);
  const preview = source.data;
  const apply = () => action.run(async () => {
    const result = await live.send<{ erased: number }>("/api/phase7/admin/retention/apply", "POST", { days, expected_count: preview?.count });
    setTyped("");
    source.reload();
    return result;
  }, "Deleted. These candidates' data is gone and their accounts are closed.");
  return (
    <div className="stack">
      <Notice>
        Candidate data should not be kept forever. This finds candidates whose applications are <strong>all closed</strong> (hired, rejected
        or withdrawn) and who have had <strong>no activity</strong> for the period you choose. Staff and Super Admins are never included.
        Ask a lawyer how long you must or may keep records under India&apos;s data protection law.
      </Notice>
      <div className="toolbar !mb-0">
        <select aria-label="No activity for" className="control" value={days} onChange={(event) => { setDays(Number(event.target.value)); setTyped(""); }}>
          {[180, 365, 730, 1095].map((d) => <option key={d} value={d}>No activity for {d >= 365 ? `${d / 365} year${d > 365 ? "s" : ""}` : `${d} days`}</option>)}
        </select>
      </div>
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      {!preview ? (!source.error && <LoadingRows />) : preview.count === 0 ? (
        <EmptyState title="Nothing to delete" text="No candidate matches this rule right now." />
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Candidate</th><th>Applications</th><th>Last activity</th></tr></thead>
              <tbody>
                {preview.candidates.map((c) => (
                  <tr key={c.user_id}><td>{c.full_name}<div className="text-muted text-xs">{c.email}</div></td><td>{c.applications}</td><td>{formatDate(c.last_activity)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <section className="panel p-5 stack">
            <h2 className="section-title">Delete these {preview.count} candidates</h2>
            <p className="text-muted text-sm">Deletes their profiles, applications, interviews, resumes and notifications, and closes their accounts. This cannot be undone.</p>
            <Field label={`Type ${preview.count} to confirm`}>
              <input className="control" inputMode="numeric" value={typed} onChange={(event) => setTyped(event.target.value)} />
            </Field>
            <div><button className="btn btn-primary" disabled={action.busy || typed !== String(preview.count)} onClick={() => void apply()}>Delete permanently</button></div>
          </section>
        </>
      )}
    </div>
  );
}
