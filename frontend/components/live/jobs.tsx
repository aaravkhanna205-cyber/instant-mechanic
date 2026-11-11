"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Pencil, Plus, Upload } from "lucide-react";
import { encoded, JOB_STATUSES, STAGES, type Application, type Category, type Job } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { StageControl } from "./applications";
import {
  ActionMessages, BackLink, EmptyState, Field, formatDate, label, LoadingRows, NeedsOrganization, NeedsRecruiter, Notice, PageHeader, Pill,
} from "./ui";

function useGate() {
  const live = useLive();
  if (!live.orgId) return <NeedsOrganization admin={live.admin} />;
  if (!live.recruiter) return <NeedsRecruiter />;
  return null;
}

export function JobsPage() {
  const live = useLive();
  const gate = useGate();
  const action = useAction();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const loader = useCallback(() => live.get<Job[]>(`${live.orgPath}/jobs`), [live]);
  const jobs = useLoad(gate ? null : loader);

  const header = (
    <PageHeader title="Jobs" subtitle="Vacancies for this organization. Only published ones are visible to candidates."
      actions={gate ? undefined : (
        <>
          <Link href="/jobs/import" className="btn"><Upload size={17} /> Import jobs</Link>
          <Link href="/jobs/new" className="btn btn-primary"><Plus size={17} /> New vacancy</Link>
        </>
      )} />
  );
  if (gate) return <>{header}{gate}</>;
  if (!jobs.data) return <>{header}{jobs.error ? <Notice kind="error">{jobs.error}</Notice> : <LoadingRows />}</>;

  const text = query.trim().toLowerCase();
  const shown = jobs.data.filter((job) =>
    (status === "all" || job.status === status) &&
    (!text || `${job.title} ${job.location || ""} ${job.category_slug}`.toLowerCase().includes(text)));
  const setJobStatus = (job: Job, next: string) =>
    action.run(async () => {
      await live.send(`${live.orgPath}/jobs/${encoded(job.id)}`, "PATCH", { status: next });
      jobs.reload();
    }, `"${job.title}" is now ${label(next).toLowerCase()}.`);

  return (
    <div className="stack">
      {header}
      <ActionMessages error={action.error || jobs.error} notice={action.notice} />
      {jobs.data.length === 0 ? (
        <EmptyState title="No vacancies yet" text="Create one, or import several from a spreadsheet."
          action={<Link href="/jobs/new" className="btn btn-primary">Create a vacancy</Link>} />
      ) : (
        <>
          <div className="toolbar">
            <input aria-label="Search jobs" className="control" placeholder="Search title or location" value={query}
              onChange={(event) => setQuery(event.target.value)} />
            <select aria-label="Filter by status" className="control" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option>
              {JOB_STATUSES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
            <span className="text-muted text-sm">{shown.length} of {jobs.data.length}</span>
          </div>
          {shown.length === 0 ? <EmptyState title="Nothing matches" text="Change the search or the status filter." /> : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Vacancy</th><th>Location</th><th>Created</th><th>Status</th><th>Change status</th></tr></thead>
                <tbody>
                  {shown.map((job) => (
                    <tr key={job.id}>
                      <td><Link href={`/jobs/${encoded(job.id)}`}>{job.title}</Link><div className="text-muted text-xs">{label(job.category_slug)}</div></td>
                      <td>{job.location || "Not set"}</td>
                      <td>{formatDate(job.created_at)}</td>
                      <td><Pill value={job.status} /></td>
                      <td>
                        <select aria-label={`Status of ${job.title}`} className="control" value={job.status} disabled={action.busy}
                          onChange={(event) => setJobStatus(job, event.target.value)}>
                          {JOB_STATUSES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function JobFormPage({ edit = false }: { edit?: boolean }) {
  const live = useLive();
  const gate = useGate();
  const params = useParams<{ id?: string }>();
  const jobId = edit ? params.id || "" : "";
  const loader = useCallback(async () => {
    const [categories, job] = await Promise.all([
      live.get<Category[]>("/api/recruitment/categories"),
      jobId ? live.get<Job>(`${live.orgPath}/jobs/${encoded(jobId)}`) : Promise.resolve(null),
    ]);
    return { categories, job };
  }, [live, jobId]);
  const source = useLoad(gate ? null : loader);
  const back = jobId ? `/jobs/${encoded(jobId)}` : "/jobs";
  const header = (
    <>
      <BackLink href={back}>{jobId ? "Back to vacancy" : "All jobs"}</BackLink>
      <PageHeader title={edit ? "Edit vacancy" : "New vacancy"}
        subtitle={edit ? "Changes apply as soon as you save." : "Saved as a draft. Publish it when it is ready for candidates."} />
    </>
  );
  if (gate) return <>{header}{gate}</>;
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  return <>{header}<JobForm categories={source.data.categories} job={source.data.job} back={back} /></>;
}

function JobForm({ categories, job, back }: { categories: Category[]; job: Job | null; back: string }) {
  const live = useLive();
  const router = useRouter();
  const action = useAction();
  const [title, setTitle] = useState(job?.title || "");
  const [category, setCategory] = useState(job?.category_slug || "");
  const [location, setLocation] = useState(job?.location || "");
  const [description, setDescription] = useState(job?.description || "");
  const [status, setStatus] = useState(job?.status || "draft");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      if (job) {
        await live.send(`${live.orgPath}/jobs/${encoded(job.id)}`, "PATCH",
          { title: title.trim(), location: location.trim() || null, description, status });
        router.push(`/jobs/${encoded(job.id)}`);
      } else {
        const created = await live.send<Job>(`${live.orgPath}/jobs`, "POST",
          { title: title.trim(), category_slug: category, location: location.trim() || null, description, status: "draft" });
        router.push(`/jobs/${encoded(created.id)}`);
      }
    });
  };

  return (
    <form className="panel p-6 stack max-w-3xl" onSubmit={submit}>
      <div className="form-grid">
        <Field label="Job title">
          <input className="control" required minLength={3} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
        </Field>
        <Field label="Role category" hint={job ? "The category cannot be changed after creation." : undefined}>
          <select className="control" required disabled={!!job} value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">Choose a role</option>
            {categories.map((item) => <option key={item.slug} value={item.slug}>{item.title} · {item.department}</option>)}
          </select>
        </Field>
        <Field label="Location">
          <input className="control" maxLength={150} placeholder="City or workshop" value={location} onChange={(event) => setLocation(event.target.value)} />
        </Field>
        {job && (
          <Field label="Status">
            <select className="control" value={status} onChange={(event) => setStatus(event.target.value)}>
              {JOB_STATUSES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
            </select>
          </Field>
        )}
      </div>
      <Field label="Description" hint="Duties, shift, experience needed. Up to 12,000 characters.">
        <textarea className="control" maxLength={12000} rows={8} value={description} onChange={(event) => setDescription(event.target.value)} />
      </Field>
      {categories.length === 0 && <Notice kind="error">No role categories found. Run the job-category seed script on the server first.</Notice>}
      {action.error && <Notice kind="error">{action.error}</Notice>}
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={action.busy}>{action.busy ? "Saving…" : job ? "Save changes" : "Save draft"}</button>
        <Link href={back} className="btn">Cancel</Link>
      </div>
    </form>
  );
}

const BOARD = STAGES.slice(0, 6);

export function JobDetailPage() {
  const live = useLive();
  const gate = useGate();
  const action = useAction();
  const { id } = useParams<{ id: string }>();
  const loader = useCallback(async () => {
    const [job, applications] = await Promise.all([
      live.get<Job>(`${live.orgPath}/jobs/${encoded(id)}`),
      live.get<Application[]>(`${live.orgPath}/applications`),
    ]);
    return { job, applications: applications.filter((item) => item.job_id === id) };
  }, [live, id]);
  const source = useLoad(gate ? null : loader);
  const back = <BackLink href="/jobs">All jobs</BackLink>;
  if (gate) return <>{back}{gate}</>;
  if (!source.data) return <>{back}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;

  const { job, applications } = source.data;
  const closed = applications.filter((item) => !BOARD.includes(item.stage as (typeof BOARD)[number]));
  const setStatus = (next: string) =>
    action.run(async () => {
      await live.send(`${live.orgPath}/jobs/${encoded(job.id)}`, "PATCH", { status: next });
      source.reload();
    }, `Vacancy is now ${label(next).toLowerCase()}.`);

  return (
    <div className="stack">
      <div>
        {back}
        <PageHeader title={job.title} subtitle={`${label(job.category_slug)} · ${job.location || "Location not set"} · Created ${formatDate(job.created_at)}`}
          actions={
            <>
              {job.status === "draft" && <button className="btn btn-primary" disabled={action.busy} onClick={() => setStatus("published")}>Publish</button>}
              {job.status === "published" && <button className="btn" disabled={action.busy} onClick={() => setStatus("paused")}>Pause</button>}
              {job.status === "paused" && <button className="btn btn-primary" disabled={action.busy} onClick={() => setStatus("published")}>Resume</button>}
              <Link href={`/jobs/${encoded(job.id)}/edit`} className="btn"><Pencil size={16} /> Edit</Link>
            </>
          } />
        <Pill value={job.status} />
      </div>
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      <section className="panel p-5">
        <h2 className="section-title mb-2">Description</h2>
        <p className="whitespace-pre-wrap">{job.description || <span className="text-muted">No description yet.</span>}</p>
      </section>
      <section>
        <h2 className="section-title mb-3">Pipeline · {applications.length} {applications.length === 1 ? "application" : "applications"}</h2>
        {applications.length === 0 ? (
          <EmptyState title="No applications yet"
            text={job.status === "published" ? "Candidates can apply from the portal, or you can import a list." : "Publish the vacancy so candidates can apply."}
            action={<Link href="/candidates/upload" className="btn">Import candidates</Link>} />
        ) : (
          <div className="board">
            {BOARD.map((stage) => {
              const items = applications.filter((item) => item.stage === stage);
              return (
                <div key={stage} className="board-column">
                  <strong>{label(stage)}</strong> <span className="text-muted">{items.length}</span>
                  {items.map((item) => (
                    <div key={item.id} className="board-card">
                      <Link href={`/candidates/${encoded(item.candidate_id)}`} className="font-semibold">{item.candidate_name}</Link>
                      <div className="text-muted text-xs mb-2">Applied {formatDate(item.applied_at)}</div>
                      <StageControl application={item} onChanged={source.reload} />
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </section>
      {closed.length > 0 && (
        <section className="panel p-5">
          <h2 className="section-title mb-3">Finished · {closed.length}</h2>
          <div className="rows">
            {closed.map((item) => (
              <div key={item.id}>
                <Link href={`/candidates/${encoded(item.candidate_id)}`} className="font-semibold">{item.candidate_name}</Link>
                <div className="flex flex-wrap items-center gap-3"><Pill value={item.stage} /><StageControl application={item} onChanged={source.reload} /></div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
