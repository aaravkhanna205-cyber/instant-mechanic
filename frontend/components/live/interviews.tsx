"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { encoded, INTERVIEW_STATUSES, type Application, type Feedback, type Interview } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import {
  ActionMessages, BackLink, EmptyState, Field, formatDateTime, label, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Pill,
} from "./ui";

/** Compact scheduling form for one application. */
export function ScheduleInterview({ applicationId, onScheduled }: { applicationId: string; onScheduled: () => void }) {
  const live = useLive();
  const action = useAction();
  const [when, setWhen] = useState("");
  const [url, setUrl] = useState("");
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send(`${live.orgPath}/interviews`, "POST",
        { application_id: applicationId, scheduled_at: new Date(when).toISOString(), meeting_url: url.trim() || null });
      setWhen("");
      setUrl("");
      onScheduled();
    }, "Interview scheduled.");
  };
  return (
    <form className="grid gap-2" onSubmit={submit}>
      <div className="flex flex-wrap gap-2 items-end">
        <Field label="Date and time">
          <input type="datetime-local" className="control" required value={when} onChange={(event) => setWhen(event.target.value)} />
        </Field>
        <Field label="Meeting link (optional)">
          <input type="url" className="control" maxLength={500} placeholder="https://" value={url} onChange={(event) => setUrl(event.target.value)} />
        </Field>
        <button className="btn" disabled={action.busy || !when}>{action.busy ? "Scheduling…" : "Schedule interview"}</button>
      </div>
      <ActionMessages error={action.error} notice={action.notice} />
    </form>
  );
}

function useInterviews() {
  const live = useLive();
  const allowed = !!live.orgId && live.recruiter;
  const loader = useCallback(async () => {
    const [interviews, applications] = await Promise.all([
      live.get<Interview[]>(`${live.orgPath}/interviews`),
      live.get<Application[]>(`${live.orgPath}/applications`),
    ]);
    return { interviews, applications };
  }, [live]);
  return { live, source: useLoad(allowed ? loader : null) };
}

export function InterviewsPage() {
  const { live, source } = useInterviews();
  const action = useAction();
  const [applicationId, setApplicationId] = useState("");
  const header = <PageHeader title="Interviews" subtitle="Schedule conversations and record what happened." />;
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;

  const { interviews, applications } = source.data;
  const open = applications.filter((item) => !["hired", "rejected", "withdrawn"].includes(item.stage));
  const setStatus = (interview: Interview, status: string) =>
    action.run(async () => {
      await live.send(`${live.orgPath}/interviews/${encoded(interview.id)}`, "PATCH", { status });
      source.reload();
    }, "Interview updated.");

  return (
    <div className="stack">
      {header}
      <section className="panel p-5 stack">
        <h2 className="section-title">Schedule an interview</h2>
        {open.length === 0 ? <p className="text-muted">There are no applications in progress to schedule.</p> : (
          <>
            <Field label="Application">
              <select className="control" value={applicationId} onChange={(event) => setApplicationId(event.target.value)}>
                <option value="">Choose a candidate and vacancy</option>
                {open.map((item) => <option key={item.id} value={item.id}>{item.candidate_name} — {item.job_title}</option>)}
              </select>
            </Field>
            {applicationId && <ScheduleInterview key={applicationId} applicationId={applicationId} onScheduled={source.reload} />}
          </>
        )}
      </section>
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      {interviews.length === 0 ? <EmptyState title="No interviews yet" text="Scheduled interviews will be listed here." /> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>When</th><th>Candidate</th><th>Vacancy</th><th>Feedback</th><th>Status</th><th>Change status</th></tr></thead>
            <tbody>
              {interviews.map((item) => (
                <tr key={item.id}>
                  <td><Link href={`/interviews/${encoded(item.id)}`}>{formatDateTime(item.scheduled_at)}</Link></td>
                  <td>{item.candidate_name}</td>
                  <td>{item.job_title}</td>
                  <td>{item.feedback_count || 0}</td>
                  <td><Pill value={item.status} /></td>
                  <td>
                    <select aria-label="Interview status" className="control" value={item.status} disabled={action.busy}
                      onChange={(event) => setStatus(item, event.target.value)}>
                      {INTERVIEW_STATUSES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function InterviewDetailPage() {
  const { live, source } = useInterviews();
  const { id } = useParams<{ id: string }>();
  const action = useAction();
  const [score, setScore] = useState("3");
  const [comments, setComments] = useState("");
  const allowed = !!live.orgId && live.recruiter;
  const feedbackLoader = useCallback(() => live.get<Feedback[]>(`${live.orgPath}/interviews/${encoded(id)}/feedback`), [live, id]);
  const feedback = useLoad(allowed ? feedbackLoader : null);
  const back = <BackLink href="/interviews">All interviews</BackLink>;
  if (!live.orgId) return <>{back}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{back}<NeedsRecruiter /></>;
  if (!source.data) return <>{back}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const interview = source.data.interviews.find((item) => item.id === id);
  if (!interview) return <>{back}<EmptyState title="Interview not found" /></>;
  const application = source.data.applications.find((item) => item.id === interview.application_id);
  const mine = (feedback.data || []).some((item) => item.reviewer_id === live.session.user.id);

  const setStatus = (status: string) =>
    action.run(async () => {
      await live.send(`${live.orgPath}/interviews/${encoded(id)}`, "PATCH", { status });
      source.reload();
    }, "Interview updated.");
  const addFeedback = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send(`${live.orgPath}/interviews/${encoded(id)}/feedback`, "POST", { score: Number(score), comments: comments.trim() || null });
      setComments("");
      feedback.reload();
      source.reload();
    }, "Feedback saved.");
  };

  return (
    <div className="stack">
      <div>
        {back}
        <PageHeader title={`Interview · ${interview.candidate_name}`} subtitle={`${interview.job_title} · ${formatDateTime(interview.scheduled_at)}`} />
        <Pill value={interview.status} />
      </div>
      <ActionMessages error={action.error || source.error || feedback.error} notice={action.notice} />
      <div className="split">
        <section className="panel p-5 stack">
          <h2 className="section-title">Details</h2>
          <div>
            <div className="field-label">Meeting link</div>
            {interview.meeting_url && /^https?:\/\//i.test(interview.meeting_url) ? <a className="text-link break-all" href={interview.meeting_url} target="_blank" rel="noreferrer">{interview.meeting_url}</a>
              : <span className="text-muted">Not set</span>}
          </div>
          {application && (
            <div>
              <div className="field-label">Candidate</div>
              <Link className="text-link" href={`/candidates/${encoded(application.candidate_id)}`}>{interview.candidate_name}</Link>
            </div>
          )}
          <Field label="Status">
            <select className="control" value={interview.status} disabled={action.busy} onChange={(event) => setStatus(event.target.value)}>
              {INTERVIEW_STATUSES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
          </Field>
        </section>
        <section className="panel p-5 stack">
          <h2 className="section-title">Interviewer feedback</h2>
          {(feedback.data || []).length === 0 ? <p className="text-muted">No feedback yet.</p> : (
            <div className="rows">
              {(feedback.data || []).map((item) => (
                <div key={item.id}>
                  <span><strong>{item.reviewer}</strong>{item.comments && <span className="block text-muted">{item.comments}</span>}</span>
                  <span className="badge">{item.score} / 5</span>
                </div>
              ))}
            </div>
          )}
          {mine ? <p className="text-muted text-xs">You have already given feedback for this interview.</p> : (
            <form className="stack" onSubmit={addFeedback}>
              <Field label="Your rating" hint="1 is weak, 5 is strong. This is your own judgement and is only shown to recruiters.">
                <select className="control" value={score} onChange={(event) => setScore(event.target.value)}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </Field>
              <Field label="Comments">
                <textarea className="control" maxLength={4000} value={comments} onChange={(event) => setComments(event.target.value)} />
              </Field>
              <div><button className="btn btn-primary" disabled={action.busy}>Save feedback</button></div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
