"use client";
import { useCallback, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { encoded, type ImportBatch, type ImportPreview, type Job } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { ActionMessages, Field, formatDateTime, label, Notice, Pill, RowErrors } from "./ui";

type Kind = "jobs" | "candidates";

const TEMPLATES: Record<Kind, { name: string; text: string; columns: string }> = {
  jobs: {
    name: "jobs-template.csv",
    columns: "title, category_slug (required) · description, location (optional)",
    text: "title,category_slug,description,location\nAutomotive Technician,automotive-technician,Diagnose and repair customer vehicles,Delhi\n",
  },
  candidates: {
    name: "candidates-template.csv",
    columns: "full_name, email (required) · phone, city, skills, job_title (optional)",
    text: "full_name,email,phone,city,skills,job_title\nAsha Verma,asha@example.com,9810000000,Delhi,\"Diagnostics, Brakes\",Automotive Technician\n",
  },
};

/** Upload a CSV or Excel file, review every row, then import. Nothing is written by the preview. */
export function ImportPanel({ kind, onImported }: { kind: Kind; onImported: () => void }) {
  const live = useLive();
  const action = useAction();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [jobId, setJobId] = useState("");
  const [consent, setConsent] = useState(false);
  const jobLoader = useCallback(() => live.get<Job[]>(`${live.orgPath}/jobs`), [live]);
  const jobs = useLoad(kind === "candidates" ? jobLoader : null);
  const template = TEMPLATES[kind];
  const templateHref = useMemo(() => `data:text/csv;charset=utf-8,${encodeURIComponent(template.text)}`, [template]);
  const base = `/api/admin-v3/organizations/${encoded(live.orgId)}/${kind === "jobs" ? "imports" : "candidate-imports"}`;

  const form = () => {
    const data = new FormData();
    if (file) data.append("file", file);
    if (kind === "candidates") {
      if (jobId) data.append("job_id", jobId);
      data.append("consent_confirmed", String(consent));
    }
    return data;
  };
  const runPreview = () =>
    action.run(async () => {
      setPreview(null);
      setPreview(await live.upload<ImportPreview>(`${base}/preview`, form()));
    });
  const runImport = () =>
    action.run(async () => {
      await live.upload(`${base}/commit`, form());
      setPreview(null);
      setFile(null);
      setConsent(false);
      onImported();
    }, kind === "jobs" ? "Jobs imported as drafts." : "Candidates imported at the Applied stage.");
  const reset = () => { setPreview(null); action.clear(); };

  const blocked = !preview || preview.errors.length > 0 || preview.valid_count === 0 || (kind === "candidates" && !consent);
  const sampleKeys = preview?.sample[0] ? Object.keys(preview.sample[0]) : [];
  const openJobs = (jobs.data || []).filter((job) => job.status !== "closed");

  return (
    <section className="panel p-5 stack">
      <div>
        <h2 className="section-title">Upload a file</h2>
        <p className="text-muted text-sm mt-1">
          CSV or Excel (.xlsx), up to 1,000 rows and 2 MB. Columns: {template.columns}.
        </p>
        <a className="text-link mt-2" href={templateHref} download={template.name}>
          <Download size={14} /> Download a template
        </a>
      </div>

      {kind === "candidates" && (
        <>
          <Field label="Default vacancy" hint="Used for rows where job_title is empty. A job_title in the file must match a vacancy title exactly.">
            <select className="control" value={jobId} onChange={(event) => { setJobId(event.target.value); reset(); }}>
              <option value="">No default — every row names its vacancy</option>
              {openJobs.map((job) => <option key={job.id} value={job.id}>{job.title} ({label(job.status)})</option>)}
            </select>
          </Field>
          {jobs.data && openJobs.length === 0 && <Notice kind="error">Create a vacancy first. Imported candidates are attached to a vacancy.</Notice>}
        </>
      )}

      <Field label="File">
        <input key={file ? "chosen" : "empty"} type="file" accept=".csv,.xlsx" className="control"
          onChange={(event) => { setFile(event.target.files?.[0] || null); reset(); }} />
      </Field>
      {file && <p className="text-muted text-xs">Selected: {file.name}</p>}

      {preview && (
        <div className="stack">
          <Notice kind={preview.errors.length ? "error" : "success"}>
            {preview.valid_count} valid {preview.valid_count === 1 ? "row" : "rows"}, {preview.errors.length} with problems.
            {kind === "candidates" && preview.errors.length === 0 &&
              ` ${preview.new_accounts} new ${preview.new_accounts === 1 ? "person" : "people"}, ${preview.existing_accounts} already registered.`}
            {preview.errors.length > 0 && " Fix the file and preview again; nothing is imported until every row is valid."}
          </Notice>
          <RowErrors errors={preview.errors} />
          {preview.sample.length > 0 && (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr>{sampleKeys.map((key) => <th key={key}>{label(key)}</th>)}</tr></thead>
                <tbody>
                  {preview.sample.map((row, index) => (
                    <tr key={index}>{sampleKeys.map((key) => <td key={key} className="wrap">{String(row[key] ?? "")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {kind === "candidates" && (
        <label className="flex gap-3 items-start">
          <input type="checkbox" className="mt-1" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          <span>
            I confirm these people agreed to be considered for work at {live.org?.name || "this organization"} and to be contacted about it.
            <span className="block text-muted text-xs mt-1">
              Each row becomes an application at the Applied stage. New people get an account without a password; they set one through “Forgot password”.
            </span>
          </span>
        </label>
      )}
      <ActionMessages error={action.error} notice={action.notice} />
      <div className="flex flex-wrap gap-2">
        <button className="btn" disabled={!file || action.busy} onClick={runPreview}>{action.busy && !preview ? "Checking…" : "Preview file"}</button>
        <button className="btn btn-primary" disabled={blocked || action.busy} onClick={runImport}>
          {preview && !preview.errors.length ? `Import ${preview.valid_count} ${preview.valid_count === 1 ? "row" : "rows"}` : "Import"}
        </button>
      </div>
    </section>
  );
}

export function ImportHistory({ kind, refreshKey }: { kind?: Kind; refreshKey: number }) {
  const live = useLive();
  const action = useAction();
  const loader = useCallback(
    () => live.get<ImportBatch[]>(`/api/admin-v3/organizations/${encoded(live.orgId)}/imports?refresh=${refreshKey}`),
    [live, refreshKey],
  );
  const batches = useLoad(loader);
  const shown = (batches.data || []).filter((batch) => !kind || (batch.kind || "jobs") === kind);
  const undo = (batch: ImportBatch) =>
    action.run(async () => {
      const segment = (batch.kind || "jobs") === "jobs" ? "imports" : "candidate-imports";
      await live.send(`/api/admin-v3/organizations/${encoded(live.orgId)}/${segment}/${encoded(batch.id)}/undo`, "POST");
      batches.reload();
    }, "Import undone.");

  return (
    <section className="panel p-5 stack">
      <div>
        <h2 className="section-title">Import history</h2>
        <p className="text-muted text-sm mt-1">Undo works while nothing imported has been changed: jobs still drafts without applications, candidates still at Applied without interviews.</p>
      </div>
      <ActionMessages error={action.error || batches.error} notice={action.notice} />
      {!batches.data ? <p className="text-muted">Loading…</p> : shown.length === 0 ? <p className="text-muted">No imports yet.</p> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>File</th><th>Type</th><th>When</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {shown.map((batch) => (
                <tr key={batch.id}>
                  <td className="wrap">{batch.filename}</td>
                  <td>{label(batch.kind || "jobs")}</td>
                  <td>{formatDateTime(batch.created_at)}</td>
                  <td><Pill value={batch.status} tone={batch.status === "applied" ? "green" : "grey"} /></td>
                  <td>{batch.status === "applied" ? <button className="btn" disabled={action.busy} onClick={() => undo(batch)}>Undo</button> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Import panel plus its history, kept in step. */
export function ImportWorkspace({ kind }: { kind: Kind }) {
  const [version, setVersion] = useState(0);
  return (
    <div className="stack">
      <ImportPanel kind={kind} onImported={() => setVersion((n) => n + 1)} />
      <ImportHistory kind={kind} refreshKey={version} />
    </div>
  );
}
