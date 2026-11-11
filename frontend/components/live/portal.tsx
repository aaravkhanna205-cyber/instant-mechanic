"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Moon, Sun, UserRound } from "lucide-react";
import {
  encoded, errorText, STAGES, type Application, type CandidateProfile, type DeletionRequest, type Interview, type Job,
} from "@/lib/api/phase3";
import { brand } from "@/lib/brand";
import { useAction, useLoad } from "@/lib/live/hooks";
import { isStaff, useLive } from "@/lib/live/session";
import { ActionMessages, EmptyState, Field, formatDate, formatDateTime, label, LoadingRows, Notice, PageHeader, Pill, skillList, Stat } from "./ui";

const NAV = [
  { href: "/portal", label: "Overview" },
  { href: "/portal/jobs", label: "Vacancies" },
  { href: "/portal/applications", label: "My applications" },
  { href: "/portal/interviews", label: "Interviews" },
];
type MyInterview = Interview & { job_title: string };

export function PortalShell({ children }: { children: React.ReactNode }) {
  const live = useLive();
  const path = usePathname();
  const { theme, setTheme } = useTheme();
  const [logoutError, setLogoutError] = useState("");
  return (
    <div>
      <header className="portal-bar">
        <div className="portal-bar-inner">
          <Link href="/portal" className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={brand.logoPath} alt="" width={32} height={32} />
            <strong>Instant Mechanic <span className="text-[var(--deep-orange)]">Hire</span></strong>
          </Link>
          <nav className="portal-nav" aria-label="Candidate portal">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} aria-current={path === item.href ? "page" : undefined}
                className={path === item.href ? "active" : ""}>{item.label}</Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button aria-label="Toggle dark mode" className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <details className="menu">
              <summary className="btn" aria-label="Account menu"><UserRound size={18} /><span className="hide-mobile">{live.session.user.full_name}</span></summary>
              <div className="panel menu-list">
                <div className="px-2.5 py-2 text-xs text-muted break-all">{live.session.user.email}</div>
                {isStaff(live.session) && <Link href="/dashboard">Recruiter workspace</Link>}
                <Link href="/auth-live/account">Account</Link>
                <button onClick={() => live.logout().catch((error) => setLogoutError(errorText(error)))}>Sign out</button>
              </div>
            </details>
          </div>
        </div>
      </header>
      <main className="portal-main">
        {logoutError && <div className="notice notice-error mb-4" role="alert">{logoutError}</div>}
        {children}
      </main>
    </div>
  );
}

export function PortalHomePage() {
  const live = useLive();
  const loader = useCallback(async () => {
    const [profile, applications, interviews] = await Promise.all([
      live.get<CandidateProfile>("/api/recruitment/me/candidate-profile"),
      live.get<Application[]>("/api/recruitment/me/applications"),
      live.get<MyInterview[]>("/api/recruitment/me/interviews"),
    ]);
    return { profile, applications, interviews, loadedAt: Date.now() };
  }, [live]);
  const source = useLoad(loader);
  const header = <PageHeader eyebrow="Candidate portal" title={`Hello, ${live.session.user.full_name.split(" ")[0]}`}
    subtitle="Keep your details up to date and follow your applications." />;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const { profile, applications, interviews, loadedAt } = source.data;
  const upcoming = interviews.filter((item) => item.status === "scheduled" && item.scheduled_at && new Date(item.scheduled_at).getTime() >= loadedAt);
  return (
    <div className="stack">
      {header}
      <section className="kpi-grid" aria-label="Summary">
        <Stat label="Applications" value={applications.length} />
        <Stat label="In progress" value={applications.filter((item) => !["hired", "rejected", "withdrawn"].includes(item.stage)).length} />
        <Stat label="Upcoming interviews" value={upcoming.length} />
        <Stat label="Profile" value={profile.exists ? "Saved" : "Not yet"} />
      </section>
      {applications.length === 0 && (
        <EmptyState title="You have not applied yet" text="See the open vacancies and apply to the ones that fit you."
          action={<Link href="/portal/jobs" className="btn btn-primary">See vacancies</Link>} />
      )}
      <ProfileForm profile={profile} onSaved={source.reload} />
      {isStaff(live.session)
        ? <Notice>You are signed in with a staff account. Data-deletion requests are for candidate accounts.</Notice>
        : <PrivacySection />}
    </div>
  );
}

function ProfileForm({ profile, onSaved }: { profile: CandidateProfile; onSaved: () => void }) {
  const live = useLive();
  const action = useAction();
  const [phone, setPhone] = useState(profile.phone || "");
  const [city, setCity] = useState(profile.city || "");
  const [skills, setSkills] = useState(skillList(profile.skills).join(", "));
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const list = skills.split(",").map((item) => item.trim()).filter(Boolean);
    void action.run(async () => {
      await live.send("/api/recruitment/me/candidate-profile", "PUT",
        { phone: phone.trim() || null, city: city.trim() || null, skills: Object.fromEntries(list.map((item) => [item, true])) });
      onSaved();
    }, "Profile saved.");
  };
  return (
    <form className="panel p-5 stack" onSubmit={submit}>
      <div>
        <h2 className="section-title">My profile</h2>
        <p className="text-muted text-sm mt-1">Recruiters for the vacancies you apply to can see this.</p>
      </div>
      <div className="form-grid">
        <Field label="Phone"><input className="control" type="tel" autoComplete="tel" maxLength={40} value={phone} onChange={(event) => setPhone(event.target.value)} /></Field>
        <Field label="City"><input className="control" autoComplete="address-level2" maxLength={120} value={city} onChange={(event) => setCity(event.target.value)} /></Field>
      </div>
      <Field label="Skills" hint="Separate with commas, e.g. Engine diagnostics, Brakes, Customer service">
        <input className="control" value={skills} onChange={(event) => setSkills(event.target.value)} />
      </Field>
      <ActionMessages error={action.error} notice={action.notice} />
      <div><button className="btn btn-primary" disabled={action.busy}>{action.busy ? "Saving…" : "Save profile"}</button></div>
    </form>
  );
}

function PrivacySection() {
  const live = useLive();
  const action = useAction();
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const loader = useCallback(() => live.get<DeletionRequest[]>("/api/privacy/deletion-requests/me"), [live]);
  const requests = useLoad(loader);
  const pending = (requests.data || []).find((item) => item.status === "pending");
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send("/api/privacy/deletion-requests", "POST", { reason: reason.trim() || null });
      setReason("");
      setAsking(false);
      requests.reload();
    }, "Request sent. An administrator will review it.");
  };
  const cancel = (id: string) =>
    action.run(async () => {
      await live.send(`/api/privacy/deletion-requests/${encoded(id)}/cancel`, "POST");
      requests.reload();
    }, "Request cancelled. Your data is unchanged.");
  return (
    <section className="panel p-5 stack">
      <div>
        <h2 className="section-title">Your data</h2>
        <p className="text-muted text-sm mt-1">
          You can ask us to delete your profile, applications and interview records. A person reviews each request. Once approved, it cannot be undone and your account is closed.
        </p>
      </div>
      <ActionMessages error={action.error || requests.error} notice={action.notice} />
      {pending ? (
        <div className="rows">
          <div>
            <span><strong>Deletion requested</strong><span className="block text-muted text-xs">Sent {formatDateTime(pending.created_at)} · waiting for review</span></span>
            <button className="btn" disabled={action.busy} onClick={() => cancel(pending.id)}>Cancel request</button>
          </div>
        </div>
      ) : asking ? (
        <form className="stack" onSubmit={submit}>
          <Field label="Reason (optional)">
            <textarea className="control" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" disabled={action.busy}>Send deletion request</button>
            <button type="button" className="btn" onClick={() => setAsking(false)}>Keep my data</button>
          </div>
        </form>
      ) : (
        <div><button className="btn" onClick={() => setAsking(true)}>Ask to delete my data</button></div>
      )}
      {(requests.data || []).filter((item) => item.status !== "pending").map((item) => (
        <p key={item.id} className="text-muted text-xs">
          Earlier request from {formatDate(item.created_at)}: {label(item.status)}{item.decision_note ? ` — ${item.decision_note}` : ""}
        </p>
      ))}
    </section>
  );
}

export function PortalJobsPage() {
  const live = useLive();
  const action = useAction();
  const [query, setQuery] = useState("");
  const loader = useCallback(async () => {
    const [jobs, applications] = await Promise.all([
      live.get<Job[]>("/api/recruitment/public/jobs?limit=100"),
      live.get<Application[]>("/api/recruitment/me/applications"),
    ]);
    return { jobs, applications };
  }, [live]);
  const source = useLoad(loader);
  const header = <PageHeader title="Vacancies" subtitle="Open positions at Instant Mechanic." />;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const applied = new Set(source.data.applications.map((item) => item.job_id));
  const text = query.trim().toLowerCase();
  const shown = source.data.jobs.filter((job) => !text || `${job.title} ${job.location || ""} ${job.description}`.toLowerCase().includes(text));
  const apply = (job: Job) =>
    action.run(async () => {
      await live.send(`/api/recruitment/jobs/${encoded(job.id)}/apply`, "POST");
      source.reload();
    }, `Application sent for ${job.title}.`);
  return (
    <div className="stack">
      {header}
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      {source.data.jobs.length === 0 ? <EmptyState title="No open vacancies right now" text="Please check again soon." /> : (
        <>
          <div className="toolbar !mb-0">
            <input aria-label="Search vacancies" className="control" placeholder="Search vacancies" value={query}
              onChange={(event) => setQuery(event.target.value)} />
            <span className="text-muted text-sm">{shown.length} of {source.data.jobs.length}</span>
          </div>
          {shown.length === 0 && <EmptyState title="Nothing matches" text="Try a different search." />}
          <div className="cards">
            {shown.map((job) => (
              <article key={job.id} className="panel p-5 flex flex-col gap-3">
                <div>
                  <h2 className="section-title">{job.title}</h2>
                  <p className="text-muted text-xs mt-1">{label(job.category_slug)} · {job.location || "Location to be confirmed"}</p>
                </div>
                <p className="whitespace-pre-wrap flex-1">{job.description || <span className="text-muted">No description provided.</span>}</p>
                <div>
                  {applied.has(job.id)
                    ? <Pill value="applied" tone="green" />
                    : <button className="btn btn-primary" disabled={action.busy} onClick={() => apply(job)}>Apply</button>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
      <p className="text-muted text-xs">Applying shares your profile with that vacancy&apos;s recruiters. Resume upload arrives in a later phase.</p>
    </div>
  );
}

const PATH = STAGES.slice(0, 7);

export function PortalApplicationsPage() {
  const live = useLive();
  const loader = useCallback(() => live.get<Application[]>("/api/recruitment/me/applications"), [live]);
  const applications = useLoad(loader);
  const header = <PageHeader title="My applications" subtitle="Where each application stands. A recruiter moves every stage by hand." />;
  if (!applications.data) return <>{header}{applications.error ? <Notice kind="error">{applications.error}</Notice> : <LoadingRows />}</>;
  return (
    <div className="stack">
      {header}
      {applications.data.length === 0 ? (
        <EmptyState title="No applications yet" action={<Link href="/portal/jobs" className="btn btn-primary">See vacancies</Link>} />
      ) : applications.data.map((item) => {
        const position = PATH.indexOf(item.stage as (typeof PATH)[number]);
        return (
          <section key={item.id} className="panel p-5">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h2 className="section-title">{item.job_title}</h2>
                <p className="text-muted text-xs mt-1">{item.job_location || "Location to be confirmed"} · Applied {formatDate(item.applied_at)}</p>
              </div>
              <Pill value={item.stage} />
            </div>
            {position >= 0 && (
              <ol className="steps" aria-label="Progress">
                {PATH.map((stage, index) => (
                  <li key={stage} className={index < position ? "done" : index === position ? "current" : ""}
                    aria-current={index === position ? "step" : undefined}>{label(stage)}</li>
                ))}
              </ol>
            )}
          </section>
        );
      })}
    </div>
  );
}

export function PortalInterviewsPage() {
  const live = useLive();
  const loader = useCallback(() => live.get<MyInterview[]>("/api/recruitment/me/interviews"), [live]);
  const interviews = useLoad(loader);
  const header = <PageHeader title="Interviews" subtitle="Times are shown in your device's time zone." />;
  if (!interviews.data) return <>{header}{interviews.error ? <Notice kind="error">{interviews.error}</Notice> : <LoadingRows />}</>;
  return (
    <div className="stack">
      {header}
      {interviews.data.length === 0 ? <EmptyState title="No interviews scheduled" text="When a recruiter schedules one, it appears here." /> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>When</th><th>Vacancy</th><th>Status</th><th>Meeting link</th></tr></thead>
            <tbody>
              {interviews.data.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.scheduled_at)}</td>
                  <td>{item.job_title}</td>
                  <td><Pill value={item.status} /></td>
                  <td>{item.meeting_url && /^https?:\/\//i.test(item.meeting_url) ? <a href={item.meeting_url} target="_blank" rel="noreferrer">Open link</a> : "Not set"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
