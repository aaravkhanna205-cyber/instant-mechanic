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
type Run = {
  id: string;
  application_id: string;
  job_title: string | null;
  status: string;
  attempts: number;
  steps: { name: string; done: boolean }[];
  waiting_reason: string | null;
  last_error: string | null;
  skills_to_verify: string[];
  matrix: Row[];
  flagged: { excerpt: string; part: number }[];
  summary: string | null;
  review_decision: string | null;
  review_note: string | null;
  created_at: string | null;
  disclaimer: string;
};
type ApplicationOption = { id: string; candidate_name: string; job_title: string; stage: string };

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
  running: "bg-blue-50 text-blue-800",
  failed: "bg-red-50 text-red-800",
  completed: "bg-green-50 text-green-800",
  cancelled: "bg-stone-100 text-stone-500",
};
const STEP_LABEL: Record<string, string> = {
  load_context: "Load application",
  check_resume: "Check resume",
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
    Promise.all([api<ApplicationOption[]>(`${b}/applications`), api<Run[]>(b)])
      .then(([a, r]) => {
        if (!active) return;
        setApplications(a);
        setRuns(r);
        setApplicationId((prev) => prev || a[0]?.id || "");
        setError("");
      })
      .catch((e: unknown) => {
        if (active) setError(message(e));
      });
    return () => {
      active = false;
    };
  }, [org, reload]);

  async function post(path: string, body: unknown, done: string) {
    if (!session || !base) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const run = await api<Run>(`${base}${path}`, { method: "POST", body: JSON.stringify(body) }, session.csrf_token);
      setOpen(run);
      setCorrections({});
      setNote("");
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
            <h1 className="text-2xl font-bold md:text-3xl">Resume Review workflow</h1>
            <p className="text-sm text-stone-600">Agent prepares resume evidence. A recruiter reviews it. Nothing is sent and no stage changes.</p>
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

        <section className="grid gap-4 rounded-2xl border border-amber-200 bg-white p-5 md:grid-cols-[1fr_2fr_auto] md:items-end">
          <label className="text-sm font-semibold">
            Organization
            <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={org} onChange={(e) => { setOrg(e.target.value); setApplicationId(""); setOpen(null); }}>
              {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">
            Application
            <select className="mt-1 w-full rounded-lg border border-amber-200 bg-white p-2" value={applicationId} onChange={(e) => setApplicationId(e.target.value)}>
              {applications.length === 0 && <option value="">No applications in this organization yet</option>}
              {applications.map((a) => (
                <option key={a.id} value={a.id}>{a.candidate_name} · {a.job_title} · {a.stage}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !applicationId}
            onClick={() => post("", { application_id: applicationId }, "Workflow started. See the result below.")}
            className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50"
          >
            Run resume review
          </button>
        </section>

        <section className="rounded-2xl border border-amber-200 bg-white">
          <div className="flex items-center justify-between border-b border-amber-100 px-5 py-3">
            <h2 className="font-bold">Workflow runs</h2>
            <button type="button" className="text-sm font-semibold text-amber-800 underline" onClick={() => setReload((n) => n + 1)}>Refresh</button>
          </div>
          {runs.length === 0 ? (
            <p className="p-5 text-sm text-stone-500">No runs yet. Pick an application above and click Run resume review.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-amber-50 text-xs uppercase text-stone-600">
                  <tr><th className="p-3">Job</th><th className="p-3">Status</th><th className="p-3">Progress</th><th className="p-3">Started</th><th className="p-3" /></tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className={`border-t border-amber-100 ${open?.id === r.id ? "bg-amber-50" : ""}`}>
                      <td className="p-3">{r.job_title ?? "—"}</td>
                      <td className="p-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${RUN_STYLE[r.status] ?? ""}`}>{r.status.replace("_", " ")}</span></td>
                      <td className="p-3">{r.steps.filter((s) => s.done).length} / {r.steps.length}</td>
                      <td className="p-3">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                      <td className="p-3 text-right"><button type="button" className="font-semibold text-amber-800 underline" onClick={() => { setOpen(r); setCorrections({}); setNote(""); }}>Open</button></td>
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
            {["failed", "waiting_resume", "running"].includes(open.status) && (
              <div className="flex gap-3">
                <button type="button" disabled={busy} onClick={() => post(`/${open.id}/resume`, {}, "Run continued from its last saved step.")} className="rounded-lg bg-[#FBBF24] px-4 py-2 font-bold text-[#1C1917] disabled:opacity-50">Resume run</button>
                <button type="button" disabled={busy} onClick={() => post(`/${open.id}/cancel`, {}, "Run cancelled.")} className="rounded-lg border border-stone-300 px-4 py-2 font-semibold">Cancel run</button>
              </div>
            )}

            {open.summary && <p className="rounded-lg border border-amber-200 bg-[#FFF4E5] p-4 text-sm leading-6">{open.summary}</p>}

            {open.matrix.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-amber-100">
                <table className="w-full text-left text-sm">
                  <thead className="bg-amber-50 text-xs uppercase text-stone-600">
                    <tr><th className="p-3">Requirement</th><th className="p-3">Agent found</th><th className="p-3">Quote from resume</th>{open.status === "waiting_review" && <th className="p-3">Your check</th>}{open.status === "completed" && <th className="p-3">Recruiter</th>}</tr>
                  </thead>
                  <tbody>
                    {open.matrix.map((row) => (
                      <tr key={row.requirement} className="border-t border-amber-100 align-top">
                        <td className="p-3 font-semibold">{row.requirement}</td>
                        <td className="p-3"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[row.status]}`}>{STATUS_LABEL[row.status]}</span></td>
                        <td className="p-3">
                          {row.excerpt ? <q className="text-stone-800">{row.excerpt}</q> : <span className="text-stone-400">—</span>}
                          {row.part && <span className="ml-2 text-xs text-stone-500">resume part {row.part}</span>}
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

            {open.flagged.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm">
                <p className="font-semibold text-red-800">Lines that look like instructions to an AI (ignored, shown for your review)</p>
                <ul className="mt-2 list-disc space-y-1 pl-5">{open.flagged.map((f, i) => <li key={i}>{f.excerpt} <span className="text-xs text-stone-500">part {f.part}</span></li>)}</ul>
              </div>
            )}

            {open.status === "waiting_review" && (
              <div className="space-y-3 border-t border-amber-100 pt-4">
                <label className="block text-sm font-semibold">
                  Review note
                  <textarea className="mt-1 w-full rounded-lg border border-amber-200 p-2" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you checked, for example: confirmed Excel skills in the screening call" />
                </label>
                <button type="button" disabled={busy || note.trim().length < 4}
                  onClick={() => post(`/${open.id}/review`, { note, corrections }, "Review saved. The application stage was not changed.")}
                  className="rounded-lg bg-[#FBBF24] px-5 py-2.5 font-bold text-[#1C1917] disabled:opacity-50">
                  {changed ? `Save review with ${changed} correction${changed > 1 ? "s" : ""}` : "Confirm evidence"}
                </button>
              </div>
            )}
            {open.status === "completed" && open.review_note && <p className="text-sm"><span className="font-semibold">Recruiter note ({open.review_decision}):</span> {open.review_note}</p>}

            <p className="text-xs text-stone-500">{open.disclaimer}</p>
          </section>
        )}
      </div>
    </main>
  );
}
