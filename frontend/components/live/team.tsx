"use client";
import { useCallback, useState } from "react";
import { encoded, ROLE_LABELS, type RoleInfo, type TeamMember } from "@/lib/api/phase3";
import { useAction, useLoad } from "@/lib/live/hooks";
import { useLive } from "@/lib/live/session";
import { ActionMessages, EmptyState, Field, LoadingRows, Notice, PageHeader, Pill } from "./ui";

type TeamData = { members: TeamMember[]; roles: RoleInfo[] };

export function TeamPage() {
  const live = useLive();
  const action = useAction();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("recruiter");
  const [confirming, setConfirming] = useState<string | null>(null);
  const base = `/api/phase7/organizations/${encoded(live.orgId)}/team`;
  const loader = useCallback(() => (live.orgId && live.fullAccess ? live.get<TeamData>(base) : Promise.resolve(null)), [live, base]);
  const source = useLoad(loader);
  const header = <PageHeader title="Team and roles" subtitle={`Who works on hiring in ${live.org?.name || "this organization"}, and what each person can do.`} />;

  if (!live.fullAccess) {
    return <>{header}<EmptyState title="Full access needed" text="Only the owner, an organization admin, the HR manager or the hiring manager can manage the team." /></>;
  }
  if (!source.data) return <>{header}{source.error ? <Notice kind="error">{source.error}</Notice> : <LoadingRows />}</>;
  const { members, roles } = source.data;
  const teamRoles = roles.filter((r) => r.team_role && (r.role !== "owner" || live.admin || live.roleLabel === "Owner"));

  const add = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(async () => {
      await live.send(base, "POST", { email: email.trim(), role });
      setEmail("");
      source.reload();
    }, `Added as ${ROLE_LABELS[role]}.`);
  };
  const change = (member: TeamMember, next: string) => action.run(async () => {
    await live.send(`${base}/${encoded(member.user_id)}`, "PATCH", { role: next });
    source.reload();
  }, `${member.full_name} is now ${ROLE_LABELS[next]}.`);
  const remove = (member: TeamMember) => action.run(async () => {
    await live.send(`${base}/${encoded(member.user_id)}`, "DELETE");
    setConfirming(null);
    source.reload();
  }, `${member.full_name} was removed from the team.`);
  const me = live.session.user.id;

  return (
    <div className="stack">
      {header}
      <ActionMessages error={action.error} notice={action.notice} />

      <section className="panel p-5 stack">
        <div>
          <h2 className="section-title">Add someone to the team</h2>
          <p className="text-muted text-sm mt-1">They must register an account first. Then enter the email they registered with.</p>
        </div>
        <form className="flex flex-wrap gap-3 items-end" onSubmit={add}>
          <Field label="Registered email">
            <input type="email" className="control" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" />
          </Field>
          <Field label="Role">
            <select className="control" value={role} onChange={(event) => setRole(event.target.value)}>
              {teamRoles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
            </select>
          </Field>
          <button className="btn btn-primary" disabled={action.busy}>Add to team</button>
        </form>
      </section>

      <section className="panel">
        <div className="p-5 pb-3"><h2 className="section-title">Team members ({members.length})</h2></div>
        {members.length === 0 ? <p className="text-muted px-5 pb-5">No team members yet.</p> : (
          <div className="table-wrap !rounded-none !border-x-0 !border-b-0">
            <table className="data-table">
              <thead><tr><th>Person</th><th>Role</th><th>Access</th><th>Action</th></tr></thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.user_id}>
                    <td>
                      {member.full_name}{member.user_id === me && <span className="text-muted"> (you)</span>}
                      <div className="text-muted text-xs">{member.email}{member.is_platform_admin ? " · Super Admin" : ""}{!member.active ? " · deactivated" : ""}</div>
                    </td>
                    <td>
                      {member.user_id === me && !live.admin ? <Pill value={ROLE_LABELS[member.role] || member.role} tone={member.full_access ? "orange" : "neutral"} /> : (
                        <select aria-label={`Role for ${member.full_name}`} className="control" value={member.role} disabled={action.busy}
                          onChange={(event) => void change(member, event.target.value)}>
                          {roles.filter((r) => r.team_role).map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
                        </select>
                      )}
                    </td>
                    <td>{member.full_access ? <Pill value="Full access" tone="orange" /> : <Pill value="Limited" tone="grey" />}</td>
                    <td>
                      {member.user_id === me && !live.admin ? <span className="text-muted text-xs">Ask another manager</span>
                        : confirming === member.user_id ? (
                          <span className="flex gap-2">
                            <button className="btn" disabled={action.busy} onClick={() => void remove(member)}>Yes, remove</button>
                            <button className="btn" onClick={() => setConfirming(null)}>Keep</button>
                          </span>
                        ) : <button className="btn" onClick={() => setConfirming(member.user_id)}>Remove</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel p-5 stack">
        <h2 className="section-title">What each role can do</h2>
        <div className="role-cards">
          {roles.map((r) => (
            <div key={r.role} className={`role-card ${r.full_access ? "full" : ""}`}>
              <strong>{r.label}</strong>
              <p className="text-muted text-sm mt-1">{r.description}</p>
            </div>
          ))}
          <div className="role-card full">
            <strong>Super Admin</strong>
            <p className="text-muted text-sm mt-1">Everything in every organization, plus organizations, platform settings, data deletion and retention. Set in Super Admin.</p>
          </div>
        </div>
        <Notice>Two safety rules: nobody can change their own role, and the last person with full access cannot be removed or downgraded.</Notice>
      </section>
    </div>
  );
}
