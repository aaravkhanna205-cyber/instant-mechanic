"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { download, encoded, STAGES, type Job, type ReportSummary, type SearchPage } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { ActionMessages, EmptyState, formatDate, label, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Pill, Stat } from "./ui";

const PERIODS = [7, 30, 90, 180, 365];
const pct = (value: number | null) => (value === null ? "No data" : `${value}%`);

export function ReportsPage() {
  const live = useLive();
  const [days, setDays] = useState(30);
  const base = `/api/phase7/organizations/${encoded(live.orgId)}`;
  const loader = useCallback(() => (live.orgId && live.recruiter ? live.get<ReportSummary>(`${base}/reports/summary?days=${days}`) : Promise.resolve(null)), [live, base, days]);
  const source = useLoad(loader);
  const header = (
    <PageHeader title="Reports" subtitle={`How hiring is going at ${live.org?.name || "your organization"}.`}
      actions={<>
        <select aria-label="Period" className="control no-print" value={days} onChange={(event) => setDays(Number(event.target.value))}>
          {PERIODS.map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
        <button className="btn no-print" onClick={() => window.print()}>Print or save as PDF</button>
      </>} />
  );
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  const r = source.data;
  return (
    <div className="stack">
      {header}
      {source.error && <Notice kind="error">{source.error}</Notice>}
      {!r ? (!source.error && <LoadingRows rows={6} />) : (
        <>
          <section className="kpi-grid" aria-label="Key numbers">
            <Stat label="New applications" value={r.applications} hint={`Last ${r.days} days`} />
            <Stat label="Open jobs" value={r.open_jobs} />
            <Stat label="Average time to hire" value={r.time_to_hire.average_days === null ? "No hires" : `${r.time_to_hire.average_days} days`}
              hint={r.time_to_hire.hires ? `${r.time_to_hire.hires} hire(s); median ${r.time_to_hire.median_days} days` : "From applying to hired"} />
            <Stat label="Interviews completed" value={pct(r.interviews.completion_rate)} hint={`${r.interviews.completed} of ${r.interviews.due} that were due`} />
          </section>

          <section className="split">
            <div className="panel p-5 stack">
              <div>
                <h2 className="section-title">Hiring funnel</h2>
                <p className="text-muted text-sm mt-1">Applications from this period, by the furthest stage they reached.</p>
              </div>
              <Funnel steps={r.funnel} />
            </div>
            <div className="panel p-5 stack">
              <h2 className="section-title">Conversion</h2>
              <div className="rows">
                <div><span>Applied → interview</span><strong>{pct(r.conversion.applied_to_interview)}</strong></div>
                <div><span>Interview → offer</span><strong>{pct(r.conversion.interview_to_offer)}</strong></div>
                <div><span>Offer → hired</span><strong>{pct(r.conversion.offer_to_hired)}</strong></div>
              </div>
              <h3 className="section-title !text-sm">Interviews that were due</h3>
              {r.interviews.due === 0 ? <p className="text-muted text-sm">None in this period.</p> : (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(r.interviews.by_status).map(([status, count]) => <span key={status}><Pill value={status} /> {count}</span>)}
                </div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="p-5 pb-3"><h2 className="section-title">By job</h2></div>
            {r.jobs.length === 0 ? <p className="text-muted px-5 pb-5">No jobs yet.</p> : (
              <div className="table-wrap !rounded-none !border-x-0 !border-b-0">
                <table className="data-table">
                  <thead><tr><th>Job</th><th>Status</th><th>Applications</th><th>Interviewed</th><th>Offers</th><th>Hired</th></tr></thead>
                  <tbody>
                    {r.jobs.map((job) => (
                      <tr key={job.job_id}>
                        <td><Link href={`/jobs/${encoded(job.job_id)}`}>{job.title}</Link></td>
                        <td><Pill value={job.status} /></td>
                        <td>{job.applications}</td><td>{job.interviewed}</td><td>{job.offers}</td><td>{job.hired}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel p-5 stack">
            <h2 className="section-title">Team activity</h2>
            {r.activity.length === 0 ? <p className="text-muted text-sm">No stage changes in this period.</p> : (
              <div className="rows">
                {r.activity.map((a) => <div key={a.name}><span>{a.name}</span><strong>{a.stage_changes} stage change(s)</strong></div>)}
              </div>
            )}
          </section>
        </>
      )}
      <FindApplications />
    </div>
  );
}

function Funnel({ steps }: { steps: { stage: string; count: number }[] }) {
  const top = Math.max(1, steps[0]?.count || 0);
  if (!steps[0]?.count) return <p className="text-muted text-sm">No applications in this period.</p>;
  return (
    <ul className="funnel">
      {steps.map((step, i) => {
        const prev = i ? steps[i - 1].count : 0;
        const drop = i && prev ? Math.round(((prev - step.count) * 100) / prev) : null;
        return (
          <li key={step.stage}>
            <span>{label(step.stage)}</span>
            <span className="bar-track">{step.count > 0 && <span className="bar-fill" style={{ width: `${(step.count / top) * 100}%` }} />}</span>
            <strong className="text-right">{step.count}</strong>
            <span className="drop">{drop ? `−${drop}%` : ""}</span>
          </li>
        );
      })}
    </ul>
  );
}

function FindApplications() {
  const live = useLive();
  const action = useAction();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("");
  const [jobId, setJobId] = useState("");
  const [page, setPage] = useState(1);
  const base = `/api/phase7/organizations/${encoded(live.orgId)}`;
  const filters = new URLSearchParams({ ...(query ? { q: query } : {}), ...(stage ? { stage } : {}), ...(jobId ? { job_id: jobId } : {}) });
  const filterText = filters.toString();
  const loader = useCallback(async () => {
    if (!live.orgId || !live.recruiter) return null;
    const [results, jobs] = await Promise.all([
      live.get<SearchPage>(`${base}/applications/search?page=${page}&page_size=25${filterText ? `&${filterText}` : ""}`),
      live.get<Job[]>(`${live.orgPath}/jobs`),
    ]);
    return { results, jobs };
  }, [live, base, page, filterText]);
  const source = useLoad(loader);
  const exportCsv = (kind: string) => action.run(
    () => download(`${base}/exports/${kind}.csv${kind === "applications" && filterText ? `?${filterText}` : ""}`, `instant-mechanic-${kind}.csv`),
    "Download started.",
  );
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(1);
    setQuery(q.trim());
  };
  if (!live.orgId || !live.recruiter) return null;
  const data = source.data;
  return (
    <section className="panel p-5 stack no-print">
      <div className="flex flex-wrap justify-between gap-3 items-start">
        <div>
          <h2 className="section-title">Find applications</h2>
          <p className="text-muted text-sm mt-1">Search by name, email, phone, city or job. Download the result as a spreadsheet (CSV).</p>
        </div>
        {live.fullAccess && (
          <div className="flex flex-wrap gap-2">
            <button className="btn" disabled={action.busy} onClick={() => void exportCsv("applications")}>Download these applications</button>
            <button className="btn" disabled={action.busy} onClick={() => void exportCsv("candidates")}>All candidates</button>
            <button className="btn" disabled={action.busy} onClick={() => void exportCsv("interviews")}>All interviews</button>
          </div>
        )}
      </div>
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      <form className="toolbar !mb-0" onSubmit={submit}>
        <input aria-label="Search applications" className="control" placeholder="Name, email, phone, city or job" value={q} onChange={(event) => setQ(event.target.value)} />
        <select aria-label="Stage" className="control" value={stage} onChange={(event) => { setStage(event.target.value); setPage(1); }}>
          <option value="">All stages</option>
          {STAGES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
        <select aria-label="Job" className="control" value={jobId} onChange={(event) => { setJobId(event.target.value); setPage(1); }}>
          <option value="">All jobs</option>
          {(data?.jobs || []).map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
        </select>
        <button className="btn btn-primary">Search</button>
        {(query || stage || jobId) && <button type="button" className="btn" onClick={() => { setQ(""); setQuery(""); setStage(""); setJobId(""); setPage(1); }}>Clear</button>}
      </form>
      {!live.fullAccess && <p className="text-muted text-xs">Spreadsheet downloads contain personal data, so only full-access roles can download them.</p>}
      {!data ? (!source.error && <LoadingRows />) : data.results.total === 0 ? <EmptyState title="No matching applications" /> : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Candidate</th><th>Job</th><th>Stage</th><th>City</th><th>Applied</th></tr></thead>
              <tbody>
                {data.results.items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.candidate_name}<div className="text-muted text-xs">{row.candidate_email}{row.phone ? ` · ${row.phone}` : ""}</div></td>
                    <td>{row.job_title}</td>
                    <td><Pill value={row.stage} /></td>
                    <td>{row.city || "—"}</td>
                    <td>{formatDate(row.applied_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <span className="text-muted text-sm">{data.results.total} found · page {data.results.page} of {data.results.pages}</span>
            <span className="flex gap-2">
              <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
              <button className="btn" disabled={page >= data.results.pages} onClick={() => setPage((p) => p + 1)}>Next</button>
            </span>
          </div>
        </>
      )}
    </section>
  );
}
