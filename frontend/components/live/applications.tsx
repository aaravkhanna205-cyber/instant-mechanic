"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { encoded, STAGES, type Application, type StageChange } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { formatDate, formatDateTime, label, Notice, Pill } from "./ui";

/** A person picks the new stage and confirms it; nothing moves automatically. */
export function StageControl({ application, onChanged, withNote = false }: { application: Application; onChanged: () => void; withNote?: boolean }) {
  const live = useLive();
  const action = useAction();
  const [stage, setStage] = useState(application.stage);
  const [note, setNote] = useState("");
  const save = () =>
    action.run(async () => {
      await live.send(`${live.orgPath}/applications/${encoded(application.id)}/stage`, "PATCH", { stage, note: note.trim() || null });
      setNote("");
      onChanged();
    });
  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap gap-2 items-center">
        <select aria-label="Move to stage" className="control" value={stage} onChange={(event) => setStage(event.target.value)}>
          {STAGES.map((value) => <option key={value} value={value}>{label(value)}</option>)}
        </select>
        {withNote && (
          <input aria-label="Note for this change" className="control flex-1 min-w-40" maxLength={2000} placeholder="Note (optional)"
            value={note} onChange={(event) => setNote(event.target.value)} />
        )}
        <button className="btn" disabled={action.busy || stage === application.stage} onClick={save}>
          {action.busy ? "Saving…" : "Move"}
        </button>
      </div>
      {action.error && <Notice kind="error">{action.error}</Notice>}
    </div>
  );
}

export function StageHistory({ applicationId }: { applicationId: string }) {
  const live = useLive();
  const loader = useCallback(
    () => live.get<StageChange[]>(`${live.orgPath}/applications/${encoded(applicationId)}/history`),
    [live, applicationId],
  );
  const history = useLoad(loader);
  if (history.error) return <Notice kind="error">{history.error}</Notice>;
  if (!history.data) return <p className="text-muted text-xs">Loading history…</p>;
  return (
    <ol className="grid gap-2 text-sm">
      {history.data.map((change) => (
        <li key={change.id}>
          <strong>{change.previous_stage ? `${label(change.previous_stage)} → ${label(change.new_stage)}` : label(change.new_stage)}</strong>
          <span className="text-muted"> · {formatDateTime(change.changed_at)}{change.changed_by ? ` · ${change.changed_by}` : ""}</span>
          {change.note && <div className="text-muted">{change.note}</div>}
        </li>
      ))}
    </ol>
  );
}

export function ApplicationsTable({ applications, onChanged, showJob = true, showCandidate = true, canEdit }: {
  applications: Application[]; onChanged: () => void; showJob?: boolean; showCandidate?: boolean; canEdit: boolean;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {showCandidate && <th>Candidate</th>}
            {showJob && <th>Vacancy</th>}
            <th>Applied</th>
            <th>Stage</th>
            {canEdit && <th>Move to</th>}
          </tr>
        </thead>
        <tbody>
          {applications.map((application) => (
            <tr key={application.id}>
              {showCandidate && (
                <td>
                  <Link href={`/candidates/${encoded(application.candidate_id)}`}>{application.candidate_name || "Candidate"}</Link>
                  <div className="text-muted text-xs">{application.candidate_email}</div>
                </td>
              )}
              {showJob && <td><Link href={`/jobs/${encoded(application.job_id)}`}>{application.job_title || "Vacancy"}</Link></td>}
              <td>{formatDate(application.applied_at)}</td>
              <td><Pill value={application.stage} /></td>
              {canEdit && <td><StageControl application={application} onChanged={onChanged} /></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
