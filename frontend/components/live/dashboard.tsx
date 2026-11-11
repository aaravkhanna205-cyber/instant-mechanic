"use client";
import Link from "next/link";
import { useCallback } from "react";
import { Plus, Upload } from "lucide-react";
import { STAGES, type Analytics, type Application, type Interview, type Job } from "@/lib/api/phase3";
import { useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { BarList, EmptyState, formatDate, formatDateTime, label, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Pill, Stat } from "./ui";

type Overview = { stats: Analytics; jobs: Job[]; applications: Application[]; interviews: Interview[]; loadedAt: number };

export function DashboardPage() {
  const live = useLive();
  const ready = live.orgId && live.recruiter;
  const loader = useCallback(async (): Promise<Overview> => {
    const [stats, jobs, applications, interviews] = await Promise.all([
      live.get<Analytics>(`${live.orgPath}/analytics`),
      live.get<Job[]>(`${live.orgPath}/jobs`),
      live.get<Application[]>(`${live.orgPath}/applications`),
      live.get<Interview[]>(`${live.orgPath}/interviews`),
    ]);
    return { stats, jobs, applications, interviews, loadedAt: Date.now() };
  }, [live]);
  const overview = useLoad(ready ? loader : null);
  const firstName = live.session.user.full_name.split(" ")[0];

  const header = (
    <PageHeader eyebrow={live.org?.name || "Recruiter overview"} title={`Welcome, ${firstName}`}
      subtitle="Live figures from your hiring pipeline."
      actions={ready ? (
        <>
          <Link href="/candidates/upload" className="btn"><Upload size={17} /> Import candidates</Link>
          <Link href="/jobs/new" className="btn btn-primary"><Plus size={17} /> New vacancy</Link>
        </>
      ) : undefined} />
  );
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  if (!overview.data) return <>{header}{overview.error ? <Notice kind="error">{overview.error}</Notice> : <LoadingRows rows={6} />}</>;

  const { stats, jobs, applications, interviews, loadedAt: now } = overview.data;
  const upcoming = interviews
    .filter((item) => item.status === "scheduled" && item.scheduled_at && new Date(item.scheduled_at).getTime() >= now)
    .sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime())
    .slice(0, 5);
  const open = stats.job_statuses.published || 0;
  const active = applications.filter((item) => !["hired", "rejected", "withdrawn"].includes(item.stage)).length;

  return (
    <div className="stack">
      {header}
      {overview.error && <Notice kind="error">{overview.error}</Notice>}
      <section aria-label="Key figures" className="kpi-grid">
        <Stat label="Open vacancies" value={open} hint={`${stats.jobs} in total, including drafts`} />
        <Stat label="Applications" value={stats.applications} hint={`${active} still in progress`} />
        <Stat label="Candidates" value={stats.candidates} hint="People who applied here" />
        <Stat label="Interviews" value={stats.interviews} hint={`${upcoming.length} coming up`} />
      </section>

      <section className="dash-grid">
        <div className="panel p-5">
          <h2 className="section-title">Hiring pipeline</h2>
          <p className="text-xs text-muted mt-1 mb-4">Applications at each stage</p>
          <BarList items={STAGES.map((stage) => ({ name: label(stage), value: stats.stages[stage] || 0 }))}
            emptyText="No applications yet. They appear here as soon as someone applies." />
        </div>
        <div className="panel p-5">
          <h2 className="section-title">Upcoming interviews</h2>
          <p className="text-xs text-muted mt-1 mb-4">Next five scheduled</p>
          {upcoming.length === 0 ? <p className="text-muted">Nothing scheduled.</p> : (
            <div className="rows">
              {upcoming.map((item) => (
                <Link key={item.id} href={`/interviews/${item.id}`}>
                  <span><strong>{item.candidate_name}</strong><span className="block text-muted text-xs">{item.job_title}</span></span>
                  <span className="text-sm">{formatDateTime(item.scheduled_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="dash-grid">
        <div className="panel p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="section-title">Latest applications</h2>
            <Link href="/candidates" className="text-link">All candidates</Link>
          </div>
          {applications.length === 0 ? <p className="text-muted">No applications yet.</p> : (
            <div className="rows">
              {applications.slice(0, 6).map((item) => (
                <Link key={item.id} href={`/candidates/${item.candidate_id}`}>
                  <span><strong>{item.candidate_name}</strong><span className="block text-muted text-xs">{item.job_title} · {formatDate(item.applied_at)}</span></span>
                  <Pill value={item.stage} />
                </Link>
              ))}
            </div>
          )}
        </div>
        <div className="panel p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="section-title">Vacancies</h2>
            <Link href="/jobs" className="text-link">All jobs</Link>
          </div>
          {jobs.length === 0 ? <p className="text-muted">No vacancies yet.</p> : (
            <div className="rows">
              {jobs.slice(0, 6).map((job) => (
                <Link key={job.id} href={`/jobs/${job.id}`}>
                  <strong>{job.title}</strong>
                  <Pill value={job.status} />
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {jobs.length === 0 && (
        <EmptyState title="Start with your first vacancy" text="Create a draft, publish it, and candidates can apply from the portal."
          action={<Link href="/jobs/new" className="btn btn-primary">Create a vacancy</Link>} />
      )}
      <p className="text-muted text-xs">People make every hiring decision here. Nothing is scored, ranked or rejected automatically.</p>
    </div>
  );
}
