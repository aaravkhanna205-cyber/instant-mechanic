"use client";
import { useCallback } from "react";
import { JOB_STATUSES, STAGES, type Analytics } from "@/lib/api/phase3";
import { useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { BarList, label, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Stat } from "./ui";

const REACHED_INTERVIEW = ["interview", "offer", "hired"];

function share(part: number, whole: number) {
  return whole ? `${Math.round((part / whole) * 100)}%` : "—";
}

export function AnalyticsPage() {
  const live = useLive();
  const allowed = !!live.orgId && live.recruiter;
  const loader = useCallback(() => live.get<Analytics>(`${live.orgPath}/analytics`), [live]);
  const stats = useLoad(allowed ? loader : null);
  const header = <PageHeader title="Analytics" subtitle="Counts from live records. Stage figures show where applications are now." />;
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  if (!stats.data) return <>{header}{stats.error ? <Notice kind="error">{stats.error}</Notice> : <LoadingRows />}</>;

  const data = stats.data;
  const count = (stage: string) => data.stages[stage] || 0;
  const reached = REACHED_INTERVIEW.reduce((sum, stage) => sum + count(stage), 0);
  const published = data.job_statuses.published || 0;

  return (
    <div className="stack">
      {header}
      <section aria-label="Key figures" className="kpi-grid">
        <Stat label="Applications" value={data.applications} hint={`${data.candidates} candidates`} />
        <Stat label="Applications per vacancy" value={data.jobs ? (data.applications / data.jobs).toFixed(1) : "—"} hint={`${data.jobs} vacancies`} />
        <Stat label="At interview or beyond" value={share(reached, data.applications)} hint={`${reached} applications`} />
        <Stat label="Hired" value={count("hired")} hint={`${share(count("hired"), data.applications)} of applications`} />
      </section>
      <div className="dash-grid">
        <section className="panel p-5">
          <h2 className="section-title mb-4">Applications by current stage</h2>
          <BarList items={STAGES.map((stage) => ({ name: label(stage), value: count(stage) }))} emptyText="No applications yet." />
        </section>
        <section className="panel p-5">
          <h2 className="section-title mb-4">Vacancies by status</h2>
          <BarList items={JOB_STATUSES.map((status) => ({ name: label(status), value: data.job_statuses[status] || 0 }))} emptyText="No vacancies yet." />
          <p className="text-muted text-xs mt-4">{published} open to candidates now · {data.interviews} interviews recorded</p>
        </section>
      </div>
      <p className="text-muted text-xs">Trends over time and source reports need more history and arrive in a later phase.</p>
    </div>
  );
}
