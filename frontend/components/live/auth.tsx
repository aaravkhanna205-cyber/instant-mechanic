"use client";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError, type Session } from "@/lib/api/phase3";
import { brand } from "@/lib/brand";
import { useAction } from "@/lib/live/hooks";
import { homeFor, isStaff, useLive } from "@/lib/live/session";
import { ActionMessages, Field, label, Notice } from "./ui";

function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-side">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={brand.logoPath} alt="" width={40} height={40} />
          <strong className="text-lg">{brand.productName}</strong>
        </div>
        <div>
          <p className="text-[#FBBF24] font-semibold text-sm tracking-wider mb-4">HIRING AT INSTANT MECHANIC</p>
          <h2>Good people,<br />hired by people.</h2>
          <p className="text-[#D6D3D1] mt-5 max-w-md">One place for vacancies, applications and interviews. Every decision is made by a person.</p>
        </div>
        <p className="text-[#A8A29E] text-xs">{brand.tagline}</p>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <h1 className="title">{title}</h1>
          <p className="text-muted mt-2">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  );
}

function safeNext(value: string | null) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "";
}

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const action = useAction();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      try {
        const session = await api<Session>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        router.replace(next || homeFor(session));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) throw new Error("That email and password do not match an active account.");
        if (error instanceof ApiError && error.status === 429) throw new Error("Too many attempts. Wait 15 minutes and try again.");
        throw error;
      }
    });
  };
  return (
    <AuthLayout title="Sign in" subtitle="Use your Instant Mechanic Hire account.">
      <form onSubmit={submit}>
        <Field label="Email">
          <input type="email" className="control" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input type="password" className="control" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        {action.error && <Notice kind="error">{action.error}</Notice>}
        <button className="btn btn-primary" disabled={action.busy}>{action.busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div className="auth-links">
        <Link href="/register">Create a candidate account</Link>
        <Link href="/forgot-password">Forgot password?</Link>
      </div>
    </AuthLayout>
  );
}

export function LoginPage() {
  return <Suspense fallback={null}><LoginForm /></Suspense>;
}

export function RegisterPage() {
  const action = useAction();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      if (password !== confirm) throw new Error("The two passwords do not match.");
      await api("/api/auth/register", { method: "POST", body: JSON.stringify({ email, full_name: fullName.trim(), password }) });
      setDone(true);
    });
  };
  if (done) {
    return (
      <AuthLayout title="Account created" subtitle="You can sign in now and apply for vacancies.">
        <div className="mt-6"><Link href="/login" className="btn btn-primary">Go to sign in</Link></div>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Create your account" subtitle="For people applying to work at Instant Mechanic.">
      <form onSubmit={submit}>
        <Field label="Full name">
          <input className="control" autoComplete="name" required minLength={2} maxLength={160} value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </Field>
        <Field label="Email">
          <input type="email" className="control" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password" hint="At least 12 characters.">
          <input type="password" className="control" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <Field label="Repeat password">
          <input type="password" className="control" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </Field>
        {action.error && <Notice kind="error">{action.error}</Notice>}
        <button className="btn btn-primary" disabled={action.busy}>{action.busy ? "Creating…" : "Create account"}</button>
      </form>
      <div className="auth-links"><Link href="/login">Already registered? Sign in</Link></div>
    </AuthLayout>
  );
}

function ResetForm() {
  const token = useSearchParams().get("token") || "";
  const action = useAction();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      try {
        if (token) await api("/api/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, password }) });
        else await api("/api/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) });
      } catch (error) {
        if (error instanceof ApiError && error.status === 503) {
          throw new Error("Password reset email is not set up on this server yet. Ask your administrator.");
        }
        throw error;
      }
    }, token ? "Password changed. You can sign in with the new one." : "If that account exists, a reset link is on its way.");
  };
  return (
    <AuthLayout title={token ? "Choose a new password" : "Reset your password"}
      subtitle={token ? "This link works once and expires after 30 minutes." : "Enter your email and we will send a reset link."}>
      <form onSubmit={submit}>
        {token ? (
          <Field label="New password" hint="At least 12 characters.">
            <input type="password" className="control" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />
          </Field>
        ) : (
          <Field label="Email">
            <input type="email" className="control" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
        )}
        <ActionMessages error={action.error} notice={action.notice} />
        <button className="btn btn-primary" disabled={action.busy}>{token ? "Update password" : "Send reset link"}</button>
      </form>
      <div className="auth-links"><Link href="/login">Back to sign in</Link></div>
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  return <Suspense fallback={null}><ResetForm /></Suspense>;
}

/** Rendered inside a LiveProvider. */
export function AccountPage() {
  const live = useLive();
  const action = useAction();
  const { user } = live.session;
  const orgName = (id: string) => live.organizations.find((org) => org.id === id)?.name || "Organization";
  return (
    <main className="gate">
      <div className="panel gate-card !max-w-xl stack">
        <div>
          <h1 className="title">Your account</h1>
          <p className="text-muted mt-1">{brand.productName}</p>
        </div>
        <dl className="stack">
          <div><dt className="field-label">Name</dt><dd>{user.full_name}</dd></div>
          <div><dt className="field-label">Email</dt><dd className="break-all">{user.email}</dd></div>
          <div>
            <dt className="field-label">Access</dt>
            <dd>
              {user.is_platform_admin && <div>Platform administrator</div>}
              {user.memberships.map((item) => <div key={item.organization_id}>{label(item.role)} · {orgName(item.organization_id)}</div>)}
              {!user.is_platform_admin && user.memberships.length === 0 && "Candidate"}
            </dd>
          </div>
        </dl>
        {action.error && <Notice kind="error">{action.error}</Notice>}
        <div className="flex flex-wrap gap-2">
          {isStaff(live.session) && <Link href="/dashboard" className="btn btn-primary">Open workspace</Link>}
          <Link href="/portal" className={`btn ${isStaff(live.session) ? "" : "btn-primary"}`}>Candidate portal</Link>
          <button className="btn" disabled={action.busy} onClick={() => action.run(live.logout)}>Sign out</button>
        </div>
      </div>
    </main>
  );
}
