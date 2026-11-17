"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { encoded, type AppNotification, type EmailLog } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { ActionMessages, EmptyState, formatDateTime, LoadingRows, Notice, PageHeader, Pill } from "./ui";

const EMAIL_TONES: Record<string, string> = { pending: "amber", outbox: "neutral", sent: "green", failed: "red", skipped: "grey" };
const EMAIL_LABELS: Record<string, string> = {
  pending: "Waiting to send", outbox: "Stored (outbox mode)", sent: "Sent", failed: "Failed", skipped: "Skipped",
};

/** Notification list shared by the workspace and the candidate portal. */
export function NotificationList({ showEmailState = false }: { showEmailState?: boolean }) {
  const live = useLive();
  const action = useAction();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const loader = useCallback(() => live.get<AppNotification[]>(`/api/notifications?limit=100${unreadOnly ? "&unread=true" : ""}`), [live, unreadOnly]);
  const source = useLoad(loader);
  const open = (item: AppNotification) => {
    if (!item.read) void live.send(`/api/notifications/${encoded(item.id)}/read`, "POST").then(source.reload).catch(() => undefined);
  };
  const readAll = () => action.run(async () => {
    await live.send("/api/notifications/read-all", "POST");
    source.reload();
  }, "All marked as read.");
  const items = source.data || [];
  const unread = items.filter((item) => !item.read).length;
  return (
    <div className="stack">
      <div className="toolbar !mb-0">
        <div className="tabs !mb-0 !border-0" role="tablist" aria-label="Which notifications">
          <button role="tab" className="tab" aria-selected={!unreadOnly} onClick={() => setUnreadOnly(false)}>All</button>
          <button role="tab" className="tab" aria-selected={unreadOnly} onClick={() => setUnreadOnly(true)}>Unread</button>
        </div>
        <span className="flex-1" />
        <button className="btn" disabled={action.busy || unread === 0} onClick={readAll}>Mark all as read</button>
      </div>
      <ActionMessages error={action.error || source.error} notice={action.notice} />
      {!source.data ? (source.error ? null : <LoadingRows />) : items.length === 0 ? (
        <EmptyState title={unreadOnly ? "Nothing unread" : "No notifications yet"} text="Updates about applications, interviews and agents appear here." />
      ) : (
        <div className="panel">
          <ul className="note-list">
            {items.map((item) => (
              <li key={item.id} className={item.read ? "" : "unread"}>
                <span className="note-dot" aria-label={item.read ? "Read" : "Unread"} />
                <div className="note-body">
                  <div>{item.message}</div>
                  <div className="text-muted text-xs mt-1 flex flex-wrap gap-x-3 gap-y-1 items-center">
                    <span>{formatDateTime(item.created_at)}</span>
                    {showEmailState && item.email_status && <span>Email: {EMAIL_LABELS[item.email_status] || item.email_status}</span>}
                  </div>
                </div>
                <div className="flex gap-2 items-center">
                  {item.link && <Link className="text-link" href={item.link} onClick={() => open(item)}>Open</Link>}
                  {!item.read && <button className="btn !min-h-0 !py-1.5" onClick={() => open(item)}>Mark read</button>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function NotificationsPage() {
  const live = useLive();
  const [tab, setTab] = useState<"mine" | "emails">("mine");
  return (
    <div>
      <PageHeader title="Notifications" subtitle="Your updates, and the emails sent to candidates." />
      {live.fullAccess && (
        <div className="tabs" role="tablist" aria-label="Notification sections">
          <button role="tab" className="tab" aria-selected={tab === "mine"} onClick={() => setTab("mine")}>My notifications</button>
          <button role="tab" className="tab" aria-selected={tab === "emails"} onClick={() => setTab("emails")}>Emails to candidates</button>
        </div>
      )}
      {tab === "mine" || !live.fullAccess ? <NotificationList /> : <EmailLogTab />}
    </div>
  );
}

function EmailLogTab() {
  const live = useLive();
  const [status, setStatus] = useState("");
  const loader = useCallback(
    () => (live.orgId ? live.get<EmailLog[]>(`/api/phase7/organizations/${encoded(live.orgId)}/emails?limit=300${status ? `&status=${status}` : ""}`) : Promise.resolve([])),
    [live, status],
  );
  const source = useLoad(loader);
  return (
    <div className="stack">
      <Notice>
        Candidates get an email when they apply, when their stage changes and when an interview is scheduled, moved or cancelled.
        In <strong>outbox</strong> mode emails are only stored here and nothing is sent. To really send them from Gmail, run
        <code>scripts\email-setup.ps1</code> on the server PC once (see docs/GMAIL-SETUP.md).
      </Notice>
      <div className="toolbar !mb-0">
        <select aria-label="Email status" className="control" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All emails</option>
          {Object.entries(EMAIL_LABELS).map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
        {source.data && <span className="text-muted text-sm">{source.data.length} shown</span>}
      </div>
      {source.error && <Notice kind="error">{source.error}</Notice>}
      {!source.data ? (source.error ? null : <LoadingRows />) : source.data.length === 0 ? (
        <EmptyState title="No candidate emails yet" text="They appear here as candidates apply and move through your stages." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>When</th><th>To</th><th>Message</th><th>Status</th></tr></thead>
            <tbody>
              {source.data.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>{item.to_name}<div className="text-muted text-xs">{item.to_email}</div></td>
                  <td className="wrap">{item.message}{item.email_error && <div className="text-xs mt-1" style={{ color: "#B91C1C" }}>{item.email_error}</div>}</td>
                  <td><Pill value={EMAIL_LABELS[item.email_status || ""] || "Unknown"} tone={EMAIL_TONES[item.email_status || ""]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
