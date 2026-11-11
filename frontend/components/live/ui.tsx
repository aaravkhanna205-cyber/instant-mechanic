"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { CircleAlert, CircleCheck, Info } from "lucide-react";
import type { RowError } from "@/lib/api/phase3";

const SPECIAL: Record<string, string> = { no_show: "No-show", trade_test: "Trade test", in_progress: "In progress" };

/** "trade_test" -> "Trade test" */
export function label(value: string) {
  if (SPECIAL[value]) return SPECIAL[value];
  const text = value.replace(/[_-]+/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Not set";
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not set";
  return new Date(value).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function skillList(skills: Record<string, unknown> | null | undefined) {
  return Object.keys(skills || {});
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1 className="title">{title}</h1>
        {subtitle && <p className="text-muted mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function BackLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className="back-link">← {children}</Link>;
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  const Icon = kind === "error" ? CircleAlert : kind === "success" ? CircleCheck : Info;
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon size={17} className="shrink-0 mt-px" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Error and success lines from useAction(). */
export function ActionMessages({ error, notice }: { error: string; notice: string }) {
  return (
    <>
      {error && <Notice kind="error">{error}</Notice>}
      {notice && <Notice kind="success">{notice}</Notice>}
    </>
  );
}

export function EmptyState({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="panel empty">
      <strong>{title}</strong>
      {text && <p className="text-muted mt-2">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function LoadingRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="panel p-5 space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

const TONES: Record<string, string> = {
  applied: "neutral", screening: "amber", shortlisted: "amber", trade_test: "orange", interview: "orange",
  offer: "teal", hired: "green", rejected: "red", withdrawn: "grey",
  draft: "grey", published: "green", paused: "amber", closed: "red",
  scheduled: "amber", in_progress: "orange", completed: "green", cancelled: "grey", no_show: "red",
  pending: "amber", undone: "grey",
};

export function Pill({ value, tone }: { value: string; tone?: string }) {
  return <span className={`pill pill-${tone || TONES[value] || "neutral"}`}>{label(value)}</span>;
}

export function Field({ label: text, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label className="field">
        <span className="field-label">{text}</span>
        {children}
      </label>
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

export function Stat({ label: text, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="panel stat">
      <span className="stat-label">{text}</span>
      <strong className="stat-value">{value}</strong>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

/** Horizontal bars for small category counts; values are shown as text too. */
export function BarList({ items, emptyText }: { items: { name: string; value: number }[]; emptyText: string }) {
  const max = Math.max(1, ...items.map((item) => item.value));
  if (!items.some((item) => item.value > 0)) return <p className="text-muted">{emptyText}</p>;
  return (
    <ul className="bar-list">
      {items.map((item) => (
        <li key={item.name}>
          <span className="bar-name">{item.name}</span>
          <span className="bar-track">{item.value > 0 && <span className="bar-fill" style={{ width: `${(item.value / max) * 100}%` }} />}</span>
          <strong className="bar-value">{item.value}</strong>
        </li>
      ))}
    </ul>
  );
}

export function RowErrors({ errors }: { errors: RowError[] }) {
  if (!errors.length) return null;
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>File row</th><th>What to fix</th></tr></thead>
        <tbody>
          {errors.map((item) => (
            <tr key={item.row}><td>{item.row}</td><td className="wrap">{item.errors.join("; ")}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function NeedsOrganization({ admin }: { admin: boolean }) {
  return (
    <EmptyState
      title="No organization yet"
      text={admin ? "Create the organization first, then add vacancies." : "A platform administrator needs to add you to an organization."}
      action={admin ? <Link className="btn btn-primary" href="/admin">Open Super Admin</Link> : undefined}
    />
  );
}

export function NeedsRecruiter() {
  return <EmptyState title="Recruiter access needed" text="Your role in this organization does not include this page. The server blocks these requests as well." />;
}
