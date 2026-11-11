"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { Upload } from "lucide-react";
import { encoded, type Application, type Candidate, type Interview } from "@/lib/api/phase3";
import { useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { StageControl, StageHistory } from "./applications";
import { ScheduleInterview } from "./interviews";
import {
  BackLink, EmptyState, formatDate, formatDateTime, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Pill, skillList,
} from "./ui";

type People = { candidates: Candidate[]; applications: Application[] };

function usePeople() {
  const live = useLive();
  const allowed = !!live.orgId && live.recruiter;
  const loader = useCallback(async (): Promise<People> => {
    const [candidates, applications] = await Promise.all([
      live.get<Candidate[]>(`${live.orgPath}/candidates`),
      live.get<Application[]>(`${live.orgPath}/applications`),
    ]);
    return { candidates, applications };
  }, [live]);
  return { live, allowed, people: useLoad(allowed ? loader : null) };
}

export function CandidatesPage() {
  const { live, allowed, people } = usePeople();
  const [query, setQuery] = useState("");
  const header = (
    <PageHeader title="Candidates" subtitle="People who have applied to this organization's vacancies."
      actions={allowed ? <Link href="/candidates/upload" className="btn btn-primary"><Upload size={17} /> Import candidates</Link> : undefined} />
  );
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  if (!people.data) return <>{header}{people.error ? <Notice kind="error">{people.error}</Notice> : <LoadingRows />}</>;

  const { candidates, applications } = people.data;
  const text = query.trim().toLowerCase();
  const shown = candidates.filter((person) =>
    !text || `${person.full_name} ${person.email} ${person.city || ""} ${skillList(person.skills).join(" ")}`.toLowerCase().includes(text));

  return (
    <div className="stack">
      {header}
      {people.error && <Notice kind="error">{people.error}</Notice>}
      {candidates.length === 0 ? (
        <EmptyState title="No candidates yet" text="They appear here after applying to a vacancy, or after you import a list."
          action={<Link href="/candidates/upload" className="btn btn-primary">Import candidates</Link>} />
      ) : (
        <>
          <div className="toolbar">
            <input aria-label="Search candidates" className="control" placeholder="Search name, city or skill" value={query}
              onChange={(event) => setQuery(event.target.value)} />
            <span className="text-muted text-sm">{shown.length} of {candidates.length}</span>
          </div>
          {shown.length === 0 ? <EmptyState title="Nothing matches" text="Try a different search." /> : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Name</th><th>Phone</th><th>City</th><th>Skills</th><th>Applications</th></tr></thead>
                <tbody>
                  {shown.map((person) => {
                    const own = applications.filter((item) => item.candidate_id === person.id);
                    return (
                      <tr key={person.id}>
                        <td><Link href={`/candidates/${encoded(person.id)}`}>{person.full_name}</Link><div className="text-muted text-xs">{person.email}</div></td>
                        <td>{person.phone || "Not given"}</td>
                        <td>{person.city || "Not given"}</td>
                        <td className="wrap">{skillList(person.skills).join(", ") || "Not given"}</td>
                        <td><div className="flex flex-wrap gap-1">{own.map((item) => <Pill key={item.id} value={item.stage} />)}</div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function CandidateDetailPage() {
  const { live, allowed, people } = usePeople();
  const { id } = useParams<{ id: string }>();
  const interviewLoader = useCallback(() => live.get<Interview[]>(`${live.orgPath}/interviews`), [live]);
  const interviews = useLoad(allowed ? interviewLoader : null);
  const [openHistory, setOpenHistory] = useState("");
  const back = <BackLink href="/candidates">All candidates</BackLink>;
  if (!live.orgId) return <>{back}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{back}<NeedsRecruiter /></>;
  if (!people.data) return <>{back}{people.error ? <Notice kind="error">{people.error}</Notice> : <LoadingRows />}</>;

  const person = people.data.candidates.find((item) => item.id === id);
  if (!person) return <>{back}<EmptyState title="Candidate not found" text="They may belong to another organization, or their data was deleted." /></>;
  const own = people.data.applications.filter((item) => item.candidate_id === id);
  const skills = skillList(person.skills);
  const reload = () => { people.reload(); interviews.reload(); };

  return (
    <div className="stack">
      <div>{back}<PageHeader title={person.full_name} subtitle={person.email} /></div>
      <section className="panel p-5">
        <h2 className="section-title mb-3">Profile</h2>
        <dl className="form-grid">
          <div><dt className="field-label">Phone</dt><dd>{person.phone || "Not given"}</dd></div>
          <div><dt className="field-label">City</dt><dd>{person.city || "Not given"}</dd></div>
        </dl>
        <div className="field-label mt-4 mb-2">Skills</div>
        {skills.length ? <div className="flex flex-wrap gap-2">{skills.map((skill) => <span key={skill} className="badge">{skill}</span>)}</div>
          : <p className="text-muted">Not given</p>}
        <p className="text-muted text-xs mt-4">Resume upload and reading arrive in Phase 4.</p>
      </section>

      <h2 className="section-title">Applications</h2>
      {own.map((application) => {
        const meetings = (interviews.data || []).filter((item) => item.application_id === application.id);
        return (
          <section key={application.id} className="panel p-5 stack">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Link href={`/jobs/${encoded(application.job_id)}`} className="font-semibold text-base">{application.job_title}</Link>
                <div className="text-muted text-xs">Applied {formatDate(application.applied_at)}</div>
              </div>
              <Pill value={application.stage} />
            </div>
            <StageControl application={application} onChanged={reload} withNote />
            <div>
              <div className="field-label mb-2">Interviews</div>
              {meetings.length === 0 ? <p className="text-muted">None scheduled.</p> : (
                <div className="rows">
                  {meetings.map((item) => (
                    <Link key={item.id} href={`/interviews/${encoded(item.id)}`}>
                      <span>{formatDateTime(item.scheduled_at)}</span><Pill value={item.status} />
                    </Link>
                  ))}
                </div>
              )}
              <div className="mt-3"><ScheduleInterview applicationId={application.id} onScheduled={reload} /></div>
            </div>
            <div>
              <button className="btn" aria-expanded={openHistory === application.id}
                onClick={() => setOpenHistory(openHistory === application.id ? "" : application.id)}>
                {openHistory === application.id ? "Hide stage history" : "Show stage history"}
              </button>
              {openHistory === application.id && <div className="mt-3"><StageHistory key={application.stage} applicationId={application.id} /></div>}
            </div>
          </section>
        );
      })}
    </div>
  );
}
