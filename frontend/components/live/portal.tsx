"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { Bell, Moon, Sun, UserRound } from "lucide-react";
import {
  encoded, errorText, STAGES, type AppNotification, type Application, type CandidateProfile, type DeletionRequest, type Job,
} from "@/lib/api/phase3";
import { brand } from "@/lib/brand";
import { useAction, useLoad } from "@/lib/live/hooks";
import { isStaff, useLive } from "@/lib/live/session";
import { NotificationList } from "./notifications";
import { ActionMessages, EmptyState, Field, formatDate, formatDateTime, label, LoadingRows, Notice, PageHeader, Pill, skillList, Stat } from "./ui";

const NAV = [
  { href: "/portal", label: "Overview" },
  { href: "/portal/jobs", label: "Jobs" },
  { href: "/portal/resume", label: "My resume" },
  { href: "/portal/applications", label: "My applications" },
  { href: "/portal/interviews", label: "Interviews" },
];
/** From /api/interview-studio/me/interviews */
type MyInterview = {
  id: string; application_id: string; job_title: string; status: string; scheduled_at: string | null; timezone: string;
  duration_minutes: number; meeting_url: string | null; candidate_response: string; questions_total: number; questions_answered: number;
};
type ResumeDoc = { id: string; filename: string; status: string; skills: { skill: string }[]; uploaded_at: string | null; error: string | null };

/** What each stage means, in plain words (same text as backend/app/phase7/messages.py). */
const STAGE_HELP: Record<string, string> = {
  applied: "We have received your application.",
  screening: "Our team is reading your application and resume.",
  shortlisted: "You are on the shortlist. We will contact you soon.",
  trade_test: "A short practical test of your skills.",
  interview: "A conversation with our team.",
  offer: "We would like to offer you the job.",
  hired: "You have joined Instant Mechanic.",
  rejected: "This application has closed. You are welcome to apply for other jobs.",
  withdrawn: "This application was withdrawn.",
};
const RESUME_STATUS: Record<string, [string, string]> = { queued: ["Being read", "amber"], ready: ["Ready", "green"], failed: ["Could not read", "red"] };

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
            <Link href="/portal/notifications" className="btn" aria-label="Notifications"
              aria-current={path === "/portal/notifications" ? "page" : undefined}><Bell size={18} /></Link>
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
    const [profile, applications, interviews, resumes, notes] = await Promise.all([
      live.get<CandidateProfile>("/api/recruitment/me/candidate-profile"),
      live.get<Application[]>("/api/recruitment/me/applications"),
      live.get<MyInterview[]>("/api/interview-studio/me/interviews"),
      live.get<ResumeDoc[]>("/api/phase4/resumes/mine").catch(() => [] as ResumeDoc[]),
      live.get<AppNotification[]>("/api/notifications?limit=5").catch(() => [] as AppNotification[]),
    ]);
    return { profile, applications, interviews, resumes, notes, loadedAt: Date.now() };
  }, [live]);
  const source = useLoad(loader);
  const header = <PageHeader eyebrow="Candidate portal" title={`Hello, ${live.session.user.full_name.split(" ")[0]}`}
    subtitle="Find a job, apply with your resume and follow every step here." />;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const { profile, applications, interviews, resumes, notes, loadedAt } = source.data;
  const upcoming = interviews.filter((item) => ["scheduled", "in_progress"].includes(item.status)
    && (!item.scheduled_at || new Date(item.scheduled_at).getTime() >= loadedAt - 3 * 3600_000));
  const toAnswer = upcoming.filter((item) => item.status === "scheduled" && item.candidate_response === "pending");
  const hasResume = resumes.some((doc) => doc.status !== "failed");
  const steps = [
    { done: profile.exists && !!profile.phone, title: "Add your phone number and city", help: "So our team can reach you.", href: "#profile", cta: "Fill in below" },
    { done: hasResume, title: "Upload your resume", help: "A PDF or Word file. You need it to apply.", href: "/portal/resume", cta: "Upload resume" },
    { done: applications.length > 0, title: "Apply for a job", help: "Pick the jobs that fit you.", href: "/portal/jobs", cta: "See jobs" },
    { done: toAnswer.length === 0, title: "Reply to interview invitations", help: toAnswer.length ? `${toAnswer.length} waiting for your reply.` : "Nothing waiting.", href: "/portal/interviews", cta: "Reply" },
  ];
  return (
    <div className="stack">
      {header}
      <section className="kpi-grid" aria-label="Summary">
        <Stat label="Applications" value={applications.length} />
        <Stat label="In progress" value={applications.filter((item) => !["hired", "rejected", "withdrawn"].includes(item.stage)).length} />
        <Stat label="Upcoming interviews" value={upcoming.length} />
        <Stat label="Resume" value={hasResume ? "Uploaded" : "Not yet"} />
      </section>
      <section className="panel p-5 stack">
        <h2 className="section-title">Your next steps</h2>
        <ol className="checklist">
          {steps.map((step, index) => (
            <li key={step.title} className={step.done ? "done" : ""}>
              <span className="tick" aria-hidden>{step.done ? "✓" : index + 1}</span>
              <span className="grow"><strong>{step.title}</strong><span className="block text-muted text-xs mt-0.5">{step.done ? "Done" : step.help}</span></span>
              {!step.done && <Link className="btn" href={step.href}>{step.cta}</Link>}
            </li>
          ))}
        </ol>
      </section>
      {upcoming.length > 0 && (
        <section className="panel p-5 stack">
          <h2 className="section-title">Upcoming interviews</h2>
          <div className="rows">
            {upcoming.map((item) => (
              <div key={item.id}>
                <span><strong>{item.job_title}</strong><span className="block text-muted text-xs">{formatDateTime(item.scheduled_at)} · {item.duration_minutes} minutes</span></span>
                <span className="flex gap-2 items-center">
                  <Pill value={item.candidate_response === "pending" ? "Reply needed" : label(item.candidate_response)}
                    tone={item.candidate_response === "pending" ? "amber" : item.candidate_response === "confirmed" ? "green" : "grey"} />
                  <Link className="btn btn-primary" href="/interview-studio/session">Open</Link>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      {notes.length > 0 && (
        <section className="panel p-5 stack">
          <div className="flex justify-between items-center gap-3">
            <h2 className="section-title">Latest updates</h2>
            <Link className="text-link" href="/portal/notifications">See all</Link>
          </div>
          <div className="rows">
            {notes.map((note) => (
              <div key={note.id}><span className={note.read ? "text-muted" : ""}>{note.message}</span><span className="text-muted text-xs">{formatDate(note.created_at)}</span></div>
            ))}
          </div>
        </section>
      )}
      <div id="profile"><ProfileForm profile={profile} onSaved={source.reload} /></div>
      {isStaff(live.session)
        ? <Notice>You are signed in with a staff account. Data-deletion requests are for candidate accounts.</Notice>
        : <PrivacySection />}
    </div>
  );
}

export function PortalNotificationsPage() {
  return (
    <div className="stack">
      <PageHeader title="Notifications" subtitle="Every update about your applications and interviews. We also email you the important ones." />
      <NotificationList />
    </div>
  );
}

export function PortalResumePage() {
  const live = useLive();
  const action = useAction();
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const loader = useCallback(() => live.get<ResumeDoc[]>("/api/phase4/resumes/mine"), [live]);
  const docs = useLoad(loader);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    form.set("consent", "true");
    void action.run(async () => {
      await live.upload("/api/phase4/resumes", form);
      setFile(null);
      setConsent(false);
      setInputKey((n) => n + 1);
      docs.reload();
    }, "Resume uploaded. It is being read now; refresh in a minute.");
  };
  const remove = (doc: ResumeDoc) => action.run(async () => {
    await live.send(`/api/phase4/resumes/${encoded(doc.id)}`, "DELETE");
    setConfirming(null);
    docs.reload();
  }, `${doc.filename} was deleted.`);
  const tooBig = !!file && file.size > 8 * 1024 * 1024;
  return (
    <div className="stack">
      <PageHeader title="My resume" subtitle="Upload your resume once. It is shared only with the jobs you apply for." />
      <ActionMessages error={action.error || docs.error} notice={action.notice} />
      <form className="panel p-5 stack" onSubmit={submit}>
        <h2 className="section-title">Upload a resume</h2>
        <Field label="Resume file" hint="PDF or Word (.docx), up to 8 MB.">
          <input key={inputKey} type="file" className="control" accept=".pdf,.docx" required onChange={(event) => setFile(event.target.files?.[0] || null)} />
        </Field>
        {tooBig && <Notice kind="error">This file is larger than 8 MB. Please upload a smaller one.</Notice>}
        <label className="flex gap-3 items-start text-sm">
          <input type="checkbox" className="mt-1" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          <span>I agree that Instant Mechanic reads my resume to match it with the jobs I apply for. A person reviews it; no decision is made automatically.</span>
        </label>
        <div><button className="btn btn-primary" disabled={action.busy || !file || !consent || tooBig}>{action.busy ? "Uploading…" : "Upload resume"}</button></div>
      </form>
      <section className="panel p-5 stack">
        <div className="flex justify-between items-center gap-3">
          <h2 className="section-title">My uploaded resumes</h2>
          <button className="btn" onClick={docs.reload}>Refresh</button>
        </div>
        {!docs.data ? (!docs.error && <LoadingRows rows={2} />) : docs.data.length === 0 ? <p className="text-muted">No resume yet.</p> : (
          <div className="rows">
            {docs.data.map((doc) => {
              const [text, tone] = RESUME_STATUS[doc.status] || [label(doc.status), "neutral"];
              return (
                <div key={doc.id}>
                  <span className="min-w-0">
                    <strong className="break-all">{doc.filename}</strong>
                    <span className="block text-muted text-xs">Uploaded {formatDate(doc.uploaded_at)}{doc.skills?.length ? ` · Skills found: ${doc.skills.map((s) => s.skill).slice(0, 8).join(", ")}` : ""}</span>
                    {doc.status === "failed" && <span className="block text-xs mt-1" style={{ color: "#B91C1C" }}>{doc.error || "We could not read this file. Please upload it again as PDF."}</span>}
                  </span>
                  <span className="flex gap-2 items-center">
                    <Pill value={text} tone={tone} />
                    {confirming === doc.id ? (
                      <>
                        <button className="btn" disabled={action.busy} onClick={() => void remove(doc)}>Yes, delete</button>
                        <button className="btn" onClick={() => setConfirming(null)}>Keep</button>
                      </>
                    ) : <button className="btn" onClick={() => setConfirming(doc.id)}>Delete</button>}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>
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
    const [jobs, applications, resumes] = await Promise.all([
      live.get<Job[]>("/api/recruitment/public/jobs?limit=100"),
      live.get<Application[]>("/api/recruitment/me/applications"),
      live.get<ResumeDoc[]>("/api/phase4/resumes/mine").catch(() => [] as ResumeDoc[]),
    ]);
    return { jobs, applications, hasResume: resumes.some((doc) => doc.status !== "failed") };
  }, [live]);
  const source = useLoad(loader);
  const header = <PageHeader title="Jobs" subtitle="Open positions at Instant Mechanic." />;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const applied = new Set(source.data.applications.map((item) => item.job_id));
  const hasResume = source.data.hasResume;
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
      {!source.data.hasResume && (
        <Notice>Upload your resume first. You need it to apply. <Link className="text-link" href="/portal/resume">Upload resume</Link></Notice>
      )}
      {source.data.jobs.length === 0 ? <EmptyState title="No open jobs right now" text="Please check again soon." /> : (
        <>
          <div className="toolbar !mb-0">
            <input aria-label="Search jobs" className="control" placeholder="Search jobs, for example mechanic or Delhi" value={query}
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
                    : hasResume
                      ? <button className="btn btn-primary" disabled={action.busy} onClick={() => apply(job)}>Apply</button>
                      : <Link className="btn" href="/portal/resume">Upload resume to apply</Link>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
      <p className="text-muted text-xs">Applying shares your profile and resume with that job&apos;s hiring team. You will get an email and a notification at every step.</p>
    </div>
  );
}

const PATH = STAGES.slice(0, 7);

export function PortalApplicationsPage() {
  const live = useLive();
  const loader = useCallback(() => live.get<Application[]>("/api/recruitment/me/applications"), [live]);
  const applications = useLoad(loader);
  const header = <PageHeader title="My applications" subtitle="Where each application stands. A person from our team moves every step." />;
  if (!applications.data) return <>{header}{applications.error ? <Notice kind="error">{applications.error}</Notice> : <LoadingRows />}</>;
  return (
    <div className="stack">
      {header}
      {applications.data.length === 0 ? (
        <EmptyState title="No applications yet" action={<Link href="/portal/jobs" className="btn btn-primary">See jobs</Link>} />
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
            <p className="stage-help">{STAGE_HELP[item.stage] || ""}</p>
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
  const action = useAction();
  const loader = useCallback(() => live.get<MyInterview[]>("/api/interview-studio/me/interviews"), [live]);
  const interviews = useLoad(loader);
  const respond = (item: MyInterview, response: "confirmed" | "declined") => action.run(async () => {
    await live.send(`/api/interview-studio/me/interviews/${encoded(item.id)}/respond`, "POST", { response });
    interviews.reload();
  }, response === "confirmed" ? "Thank you, your interview is confirmed." : "We have told the team you cannot attend.");
  const header = <PageHeader title="Interviews" subtitle="Times are shown in your device's time zone." />;
  if (!interviews.data) return <>{header}{interviews.error ? <Notice kind="error">{interviews.error}</Notice> : <LoadingRows />}</>;
  return (
    <div className="stack">
      {header}
      <ActionMessages error={action.error} notice={action.notice} />
      {interviews.data.length === 0 ? <EmptyState title="No interviews yet" text="When our team schedules one, it appears here and we email you." /> : (
        <div className="cards">
          {interviews.data.map((item) => (
            <article key={item.id} className="panel p-5 flex flex-col gap-3">
              <div className="flex justify-between gap-3 items-start">
                <div>
                  <h2 className="section-title">{item.job_title}</h2>
                  <p className="text-muted text-xs mt-1">{formatDateTime(item.scheduled_at)} · {item.duration_minutes} minutes</p>
                </div>
                <Pill value={item.status} />
              </div>
              {item.status === "scheduled" && item.candidate_response === "pending" && (
                <div className="flex flex-wrap gap-2">
                  <button className="btn btn-primary" disabled={action.busy} onClick={() => void respond(item, "confirmed")}>I will attend</button>
                  <button className="btn" disabled={action.busy} onClick={() => void respond(item, "declined")}>I cannot attend</button>
                </div>
              )}
              {item.candidate_response !== "pending" && <p className="text-sm">Your reply: <strong>{label(item.candidate_response)}</strong></p>}
              {item.questions_total > 0 && ["scheduled", "in_progress"].includes(item.status) && (
                <p className="text-sm">Online questions: {item.questions_answered} of {item.questions_total} answered.</p>
              )}
              <div className="flex flex-wrap gap-2 mt-auto">
                {["scheduled", "in_progress"].includes(item.status) && <Link className="btn" href="/interview-studio/session">Open interview</Link>}
                {item.meeting_url && /^https?:\/\//i.test(item.meeting_url) && <a className="btn" href={item.meeting_url} target="_blank" rel="noreferrer">Join video call</a>}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
