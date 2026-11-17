"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Organization, type Session } from "../../../lib/api/phase3";

type Status = "supported" | "unclear" | "missing_evidence";
type Row = {
  requirement: string;
  status: Status;
  excerpt: string | null;
  part: number | null;
  note: string | null;
  recruiter_status?: Status;
};
type Workflow = "resume_review" | "interview_summary" | "job_description" | "recruitment_analytics";
type Issue = { kind: string; severity: "fix" | "improve"; where: string; text: string; why: string; suggestion: string };
type Snapshot = { days: number; applications_current: number; applications_previous: number; open_by_stage: Record<string, number>; stuck_by_stage: Record<string, number>; interviews_overdue: number; interviews_completed: number; jobs: { title: string; status: string; current: number; previous: number }[] };
type Run = {
  id: string;
  workflow: Workflow;
  application_id: string;
  interview_id: string | null;
  job_id: string | null;
  issues: Issue[];
  draft: string | null;
  findings: { kind: string; text: string }[];
  snapshot: Snapshot | null;
  job_title: string | null;
  status: string;
  attempts: number;
  steps: { name: string; done: boolean }[];
  waiting_reason: string | null;
  last_error: string | null;
  skills_to_verify: string[];
  matrix: Row[];
  flagged: { excerpt: string; part: number }[];
  unanswered: { position: number; question: string }[];
  summary: string | null;
  review_decision: string | null;
  review_note: string | null;
  created_at: string | null;
  disclaimer: string;
};
type ApplicationOption = { id: string; candidate_name: string; job_title: string; stage: string };
type InterviewOption = { id: string; candidate_name: string; job_title: string; status: string };
type JobOption = { id: string; title: string; status: string; applications: number };
const WORKFLOWS: [Workflow, string][] = [
  ["resume_review", "Resume review"],
  ["interview_summary", "Interview summary"],
  ["job_description", "Job description"],
  ["recruitment_analytics", "Analytics"],
];
const WORKFLOW_LABEL = Object.fromEntries(WORKFLOWS) as Record<Workflow, string>;
const STAGES = ["applied", "screening", "shortlisted", "trade_test", "interview", "offer"];

const STATUS_LABEL: Record<Status, string> = {
  supported: "Text found",
  unclear: "Needs checking",
  missing_evidence: "No text found",
};
const STATUS_STYLE: Record<Status, string> = {
  supported: "bg-green-50 text-green-800 border-green-200",
  unclear: "bg-amber-50 text-amber-900 border-amber-200",
  missing_evidence: "bg-red-50 text-red-800 border-red-200",
};
const RUN_STYLE: Record<string, string> = {
  waiting_review: "bg-amber-100 text-amber-900",
  waiting_resume: "bg-stone-100 text-stone-700",
  waiting_interview: "bg-stone-100 text-stone-700",
  running: "bg-blue-50 text-blue-800",
  failed: "bg-red-50 text-red-800",
  completed: "bg-green-50 text-green-800",
  cancelled: "bg-stone-100 text-stone-500",
};
const STEP_LABEL: Record<string, string> = {
  load_context: "Load application",
  check_resume: "Check resume",
  check_completed: "Check interview finished",
  load_job: "Load job",
  check_quality: "Check wording",
  draft: "Write draft",
  load_pipeline: "Count pipeline",
  find_bottlenecks: "Find bottlenecks",
  write_report: "Write report",
  safety_scan: "Safety scan",
  build_evidence: "Match requirements",
  summarize: "Summary",
  request_review: "Ask recruiter",
};

function message(e: unknown) {
  return e instanceof ApiError ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : String(e);
}

export default function WorkflowsPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [org, setOrg] = useState("");
  const [applications, setApplications] = useState<ApplicationOption[]>([]);
  const [applicationId, setApplicationId] = useState("");
  const [workflow, setWorkflow] = useState<Workflow>("resume_review");
  const [interviews, setInterviews] = useState<InterviewOption[]>([]);
  const [interviewId, setInterviewId] = useState("");
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [jobId, setJobId] = useState("");
  const [days, setDays] = useState(30);
  const [draftText, setDraftText] = useState("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [open, setOpen] = useState<Run | null>(null);
  const [note, setNote] = useState("");
  const [corrections, setCorrections] = useState<Record<string, Status>>({});
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const base = org ? `/api/phase6/organizations/${encodeURIComponent(org)}/workflows` : "";

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const s = await api<Session>("/api/auth/me");
        const organizations = await api<Organization[]>("/api/recruitment/organizations");
        if (!active) return;
        setSession(s);
        setOrgs(organizations);
        if (organizations.length) setOrg((prev) => prev || organizations[0].id);
      } catch (e) {
        if (active) setError(message(e));
      }
    })();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!org) return;
    let active = true;
    const b = `/api/phase6/organizations/${encodeURIComponent(org)}/workflows`;
    Promise.all([api<ApplicationOption[]>(`${b}/applications`), api<InterviewOption[]>(`${b}/interviews`), api<JobOption[]>(`${b}/jobs`), api<Run[]>(b)])
      .then(([a, i, j, r]) => {
        if (!active) return;
        setApplications(a);
        setInterviews(i);
        setJobs(j);
        setJobId((prev) => prev || j[0]?.id || "");
        setRuns(r);
        setApplicationId((prev) => prev || a[0]?.id || "");
        setInterviewId((prev) => prev || i[0]?.id || "");
        setError("");
      })
      .catch((e: unknown) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [org, reload]);

  function openRun(run: Run) {
    setOpen(run);
    setCorrections({});
    setNote("");
    setDraftText(run.draft ?? "");
  }

  async function post(path: string, body: unknown, done: string) {
    if (!session || !base) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const run = await api<Run>(`${base}${path}`, { method: "POST", body: JSON.stringify(body) }, session.csrf_token);
      openRun(run);
      setInfo(done);
      setReload((n) => n + 1);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  const changed = Object.keys(corrections).length;

  return (
    <main className="min-h-screen bg-[#fffaf1] text-[#26211b]">
      <header className="border-b border-amber-200 bg-white px-4 py-5 shadow-sm md:px-10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-bold uppercase tracking-[.25em] text-amber-700">Instant Mechanic Hire</div>
            <h1 className="text-2xl font-bold md:text-3xl">Agent workflows</h1>
            <p className="text-sm text-stone-600">Agents check resumes, interview answers and job descriptions, and report on your pipeline. You review and decide; nothing is sent and no stage changes.</p>
          </div>
          <a href="/phase6" className="rounded-xl border border-amber-300 px-4 py-2 text-sm font-semibold">Back to Phase 6</a>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-5 px-4 py-7 md:px-10">
        {error && (
          <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">
            {error} {!session && <a className="underline" href="/auth-live">Sign in</a>}
          </div>
        )}
        {info && <div role="status" className="rounded-xl border border-green-300 bg-green-50 p-4 text-green-900">{info}</div>}

        <section className="space-y-4 rounded-2xl border border-amber-200 bg-white p-5">
          <div role="tablist" aria-label="Workflow" className="inline-flex flex-wrap rounded-xl border border-amber-200 bg-[#FFF4E5] p-1 text-sm font-semibold">
            {WORKFLOWS.map(([key, label]) => (
              <button key={key} type="button" role="tab" aria-selected={workflow === key} onClick={() => setWorkflow(key)}
                className={`rounded-lg px-4 py-2 ${workflow === key ? "bg-white shadow-sm" : "text-stone-600"}`}>{label}</button>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-[1fr_2fr_auto] md:items-end">
            <label className="text-sm font-semibold">
              Organization
              <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={org} onChange={(e) => { setOrg(e.target.value); setApplicationId(""); setInterviewId(""); setJobId(""); setOpen(null); }}>
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
            {workflow === "resume_review" && (
              <label className="text-sm font-semibold">
                Application
                <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
                  {applications.length === 0 && <option value="">No applications in this organization yet</option>}
                  {applications.map((a) => (
                    <option key={a.id} value={a.id}>{a.candidate_name} · {a.job_title} · {a.stage}</option>
                  ))}
                </select>
              </label>
            )}
            {workflow === "interview_summary" && (
              <label className="text-sm font-semibold">
                Interview
                <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={interviewId} onChange={(e) => setInterviewId(e.target.value)}>
                  {interviews.length === 0 && <option value="">No interviews in this organization yet</option>}
                  {interviews.map((i) => (
                    <option key={i.id} value={i.id}>{i.candidate_name} · {i.job_title} · {i.status.replace("_", " ")}</option>
                  ))}
                </select>
              </label>
            )}
            {workflow === "job_description" && (
              <label className="text-sm font-semibold">
                Job
                <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={jobId} onChange={(e) => setJobId(e.target.value)}>
                  {jobs.length === 0 && <option value="">No jobs in this organization yet</option>}
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>{j.title} · {j.status} · {j.applications} applications</option>
                  ))}
                </select>
              </label>
            )}
            {workflow === "recruitment_analytics" && (
              <label className="text-sm font-semibold">
                Period
                <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {[7, 30, 90, 180].map((d) => <option key={d} value={d}>Last {d} days</option>)}
                </select>
              </label>
            )}
            {workflow === "resume_review" && (
              <button type="button" disabled={busy || !applicationId}
                onClick={() => post("", { application_id: applicationId }, "Workflow started. See the result below.")}
                className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">Run resume review</button>
            )}
            {workflow === "interview_summary" && (
              <button type="button" disabled={busy || !interviewId}
                onClick={() => post("/interview-summary", { interview_id: interviewId }, "Workflow started. See the result below.")}
                className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">Run interview summary</button>
            )}
            {workflow === "job_description" && (
              <button type="button" disabled={busy || !jobId}
                onClick={() => post("/job-description", { job_id: jobId }, "Draft ready. Review it below; the job has not changed.")}
                className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">Check job description</button>
            )}
            {workflow === "recruitment_analytics" && (
              <button type="button" disabled={busy}
                onClick={() => post("/analytics", { days }, "Report ready. See it below.")}
                className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">Create report</button>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-amber-200 bg-white">
          <div className="flex items-center justify-between border-b border-amber-100 px-5 py-3">
            <h2 className="font-bold">Workflow runs</h2>
            <button type="button" className="text-sm font-semibold text-amber-800 underline" onClick={() => setReload((n) => n + 1)}>Refresh</button>
          </div>
          {runs.length === 0 ? (
            <p className="p-5 text-sm text-stone-500">No runs yet. Pick a workflow above and start it.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-amber-50 text-xs uppercase text-stone-600">
                  <tr><th className="p-3">Workflow</th><th className="p-3">Job</th><th className="p-3">Status</th><th className="p-3">Progress</th><th className="p-3">Started</th><th className="p-3" /></tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className={`border-t border-amber-100 ${open?.id === r.id ? "bg-amber-50" : ""}`}>
                      <td className="p-3">{WORKFLOW_LABEL[r.workflow] ?? r.workflow}</td>
                      <td className="p-3">{r.job_title ?? "—"}</td>
                      <td className="p-3"><span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${RUN_STYLE[r.status] ?? ""}`}>{r.status.replace("_", " ")}</span></td>
                      <td className="p-3">{r.steps.filter((s) => s.done).length} / {r.steps.length}</td>
                      <td className="p-3">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                      <td className="p-3 text-right"><button type="button" className="font-semibold text-amber-800 underline" onClick={() => openRun(r)}>Open</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {open && (
          <section className="space-y-5 rounded-2xl border border-amber-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-bold">{open.job_title ?? "Resume review"}</h2>
              <span className={`rounded-full px-3 py-1 text-sm font-semibold ${RUN_STYLE[open.status] ?? ""}`}>{open.status.replace("_", " ")}</span>
            </div>

            <ol className="flex flex-wrap gap-2 text-xs">
              {open.steps.map((s, i) => (
                <li key={s.name} className={`rounded-full border px-3 py-1 ${s.done ? "border-amber-300 bg-amber-50 font-semibold" : "border-stone-200 text-stone-500"}`}>
                  {i + 1}. {STEP_LABEL[s.name] ?? s.name}
                </li>
              ))}
            </ol>

            {open.waiting_reason && <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-sm">{open.waiting_reason}</p>}
            {open.last_error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{open.last_error} (attempt {open.attempts} of 5)</p>}
            {["failed", "waiting_resume", "waiting_interview", "running"].includes(open.status) && (
              <div className="flex gap-3">
                <button type="button" disabled={busy} onClick={() => post(`/${open.id}/resume`, {}, "Run continued from its last saved step.")} className="rounded-lg bg-[#FBBF24] px-4 py-2 font-bold text-[#1C1917] disabled:opacity-50">Resume run</button>
                <button type="button" disabled={busy} onClick={() => post(`/${open.id}/cancel`, {}, "Run cancelled.")} className="rounded-lg border border-stone-300 px-4 py-2 font-semibold">Cancel run</button>
              </div>
            )}

            {open.summary && <p className="rounded-lg border border-amber-200 bg-[#FFF4E5] p-4 text-sm leading-6">{open.summary}</p>}

            {open.issues.length > 0 && (
              <ul className="space-y-2">
                {open.issues.map((issue, i) => (
                  <li key={i} className={`rounded-lg border p-3 text-sm ${issue.severity === "fix" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
                    <span className={`mr-2 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold ${issue.severity === "fix" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>{issue.severity === "fix" ? "Fix" : "Improve"}</span>
                    <span className="font-semibold">{issue.where}: “{issue.text}”</span> {issue.why} <span className="text-stone-600">{issue.suggestion}</span>
                  </li>
                ))}
              </ul>
            )}

            {open.workflow === "job_description" && open.draft && (
              <label className="block text-sm font-semibold">
                Draft {open.status === "waiting_review" ? "(edit it before approving)" : ""}
                <textarea className="mt-1 w-full rounded-lg border border-amber-200 p-3 font-mono text-[13px] leading-6" rows={16}
                  value={open.status === "waiting_review" ? draftText : open.draft} readOnly={open.status !== "waiting_review"}
                  onChange={(e) => setDraftText(e.target.value)} />
              </label>
            )}

            {open.snapshot && (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-amber-100">
                  <p className="border-b border-amber-100 bg-amber-50 px-3 py-2 text-xs font-bold uppercase text-stone-600">Open applications by stage</p>
                  <table className="w-full text-sm"><tbody>
                    {STAGES.map((stage) => (
                      <tr key={stage} className="border-t border-amber-100 first:border-t-0">
                        <td className="p-2.5">{stage.replace("_", " ")}</td>
                        <td className="p-2.5 text-right font-semibold tabular-nums">{open.snapshot?.open_by_stage[stage] ?? 0}</td>
                        <td className="p-2.5 text-right text-xs text-stone-500 tabular-nums">{open.snapshot?.stuck_by_stage[stage] ? `${open.snapshot.stuck_by_stage[stage]} waiting 7+ days` : ""}</td>
                      </tr>
                    ))}
                  </tbody></table>
                </div>
                <div className="rounded-xl border border-amber-100">
                  <p className="border-b border-amber-100 bg-amber-50 px-3 py-2 text-xs font-bold uppercase text-stone-600">Applications per job (last {open.snapshot.days} days / before)</p>
                  <table className="w-full text-sm"><tbody>
                    {open.snapshot.jobs.map((j) => (
                      <tr key={j.title} className="border-t border-amber-100 first:border-t-0">
                        <td className="p-2.5">{j.title} <span className="text-xs text-stone-500">{j.status}</span></td>
                        <td className="p-2.5 text-right font-semibold tabular-nums">{j.current}</td>
                        <td className="p-2.5 text-right text-stone-500 tabular-nums">{j.previous}</td>
                      </tr>
                    ))}
                  </tbody></table>
                </div>
              </div>
            )}

            {open.findings.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
                <p className="font-semibold">What needs attention</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">{open.findings.map((f, i) => <li key={i}>{f.text}</li>)}</ul>
              </div>
            )}

            {open.matrix.length > 0 && (

              <div className="overflow-x-auto rounded-xl border border-amber-100">
                <table className="w-full text-left text-sm">
                  <thead className="bg-amber-50 text-xs uppercase text-stone-600">
                    <tr><th className="p-3">Requirement</th><th className="p-3">Agent found</th><th className="p-3">{open.workflow === "interview_summary" ? "Quote from answers" : "Quote from resume"}</th>{open.status === "waiting_review" && <th className="p-3">Your check</th>}{open.status === "completed" && <th className="p-3">Recruiter</th>}</tr>
                  </thead>
                  <tbody>
                    {open.matrix.map((row) => (
                      <tr key={row.requirement} className="border-t border-amber-100 align-top">
                        <td className="p-3 font-semibold">{row.requirement}</td>
                        <td className="p-3"><span className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[row.status]}`}>{STATUS_LABEL[row.status]}</span></td>
                        <td className="p-3">
                          {row.excerpt ? <q className="text-stone-800">{row.excerpt}</q> : <span className="text-stone-400">—</span>}
                          {row.part && <span className="ml-2 text-xs text-stone-500">{open.workflow === "interview_summary" ? `answer to question ${row.part}` : `resume part ${row.part}`}</span>}
                          {row.note && <p className="mt-1 text-xs text-stone-500">{row.note}</p>}
                        </td>
                        {open.status === "waiting_review" && (
                          <td className="p-3">
                            <select aria-label={`Your check for ${row.requirement}`} className="rounded-lg border border-amber-200 bg-white p-1.5" value={corrections[row.requirement] ?? row.status}
                              onChange={(e) => {
                                const value = e.target.value as Status;
                                setCorrections((prev) => {
                                  const next = { ...prev };
                                  if (value === row.status) delete next[row.requirement];
                                  else next[row.requirement] = value;
                                  return next;
                                });
                              }}>
                              {(Object.keys(STATUS_LABEL) as Status[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                            </select>
                          </td>
                        )}
                        {open.status === "completed" && <td className="p-3">{row.recruiter_status ? STATUS_LABEL[row.recruiter_status] : "—"}</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {open.skills_to_verify.length > 0 && (
              <p className="text-sm"><span className="font-semibold">Skills mentioned, to verify:</span> {open.skills_to_verify.join(", ")}</p>
            )}

            {open.unanswered.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
                <p className="font-semibold">Questions with no answer or a very short one</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">{open.unanswered.map((u) => <li key={u.position}>Question {u.position}: {u.question}</li>)}</ul>
              </div>
            )}

            {open.flagged.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm">
                <p className="font-semibold text-red-800">Lines that look like instructions to an AI (ignored, shown for your review)</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">{open.flagged.map((f, i) => <li key={i}>{f.excerpt} <span className="text-xs text-stone-500">{open.workflow === "interview_summary" ? `question ${f.part}` : `part ${f.part}`}</span></li>)}</ul>
              </div>
            )}

            {open.status === "waiting_review" && (
              <div className="space-y-3 border-t border-amber-100 pt-4">
                <label className="block text-sm font-semibold">
                  Review note
                  <textarea className="mt-1 w-full rounded-lg border border-amber-200 p-2" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={open.workflow === "job_description" ? "What you changed, for example: removed age limit, added salary" : "What you checked, for example: confirmed Excel skills in the screening call"} />
                </label>
                {open.workflow === "job_description" ? (
                  <div className="flex flex-wrap gap-3">
                    <button type="button" disabled={busy || note.trim().length < 4 || draftText.trim().length < 20}
                      onClick={() => post(`/${open.id}/review`, { note, apply_description: draftText }, "Job description updated. The job's status, title and requirements were not changed.")}
                      className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">Approve and update job description</button>
                    <button type="button" disabled={busy || note.trim().length < 4}
                      onClick={() => post(`/${open.id}/review`, { note }, "Review saved. The job was not changed.")}
                      className="rounded-lg border border-stone-300 px-5 py-2.5 font-semibold disabled:opacity-50">Keep job unchanged</button>
                  </div>
                ) : (
                  <button type="button" disabled={busy || note.trim().length < 4}
                    onClick={() => post(`/${open.id}/review`, { note, corrections }, "Review saved. The application stage was not changed.")}
                    className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">
                    {changed ? `Save review with ${changed} correction${changed > 1 ? "s" : ""}` : "Confirm evidence"}
                  </button>
                )}
              </div>
            )}
            {open.status === "completed" && open.review_note && <p className="text-sm"><span className="font-semibold">Recruiter note ({open.review_decision}):</span> {open.review_note}</p>}
            {open.workflow === "interview_summary" && ["waiting_review", "completed"].includes(open.status) && (
              <a href="/interview-studio" className="inline-block rounded-lg border border-amber-300 px-4 py-2 text-sm font-semibold">Record your hiring decision in Interview Studio</a>
            )}

            <p className="text-xs text-stone-500">{open.disclaimer}</p>
          </section>
        )}
      </div>
    </main>
  );
}
