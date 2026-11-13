"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Session, type Organization } from "../../lib/api/phase3";

type Proposal = { id:string; kind:string; title:string; draft:string; state:string; created_at:string|null; attempts:number; last_error:string|null };
type Task = { id:string; title:string; status:string; due_at:string|null };
type Evidence = { id:string; title:string; excerpt:string; matched_terms:number };
type Event = { id:string; event:string; created_at:string|null };
type Delivery = { proposal_id:string; mode:string; status:string };
type Overview = { total_proposals:number; open_tasks:number; proposal_counts:Record<string,number>; disclaimer:string };
export default function Phase6Page() {
  const [session,setSession] = useState<Session|null>(null);
  const [orgs,setOrgs] = useState<Organization[]>([]);
  const [org,setOrg] = useState("");
  const [tab,setTab] = useState("approvals");
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [proposals,setProposals] = useState<Proposal[]>([]);
  const [tasks,setTasks] = useState<Task[]>([]);
  const [events,setEvents] = useState<Event[]>([]);
  const [deliveries,setDeliveries] = useState<Delivery[]>([]);
  const [overview,setOverview] = useState<Overview|null>(null);
  const [kind,setKind] = useState("interview_reminder");
  const [targetType,setTargetType] = useState("interview");
  const [targetId,setTargetId] = useState("");
  const [taskTitle,setTaskTitle] = useState("");
  const [docTitle,setDocTitle] = useState("");
  const [docBody,setDocBody] = useState("");
  const [query,setQuery] = useState("");
  const [evidence,setEvidence] = useState<Evidence[]>([]);
  const [editDraft,setEditDraft] = useState<Record<string,string>>({});
  const [success,setSuccess] = useState("");
  const base = org ? `/api/phase6/organizations/${encodeURIComponent(org)}` : "";
  const load = useCallback(async (selected: string) => {
    try {
      const b = `/api/phase6/organizations/${encodeURIComponent(selected)}`;
      const [p,t,e,d,o] = await Promise.all([
        api<Proposal[]>(`${b}/proposals`),api<Task[]>(`${b}/tasks`),
        api<Event[]>(`${b}/events`),api<Delivery[]>(`${b}/deliveries`),api<Overview>(`${b}/overview`)
      ]);
      setProposals(p);setTasks(t);setEvents(e);setDeliveries(d);setOverview(o);setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Failed loading workflow data"); }
  },[]);
  useEffect(() => {
    let active = true;
    (async () => {try {
      const s = await api<Session>("/api/auth/me");
      const organizations = await api<Organization[]>("/api/recruitment/organizations");
      if (!active) return;
      setSession(s);setOrgs(organizations);
      if (organizations.length) setOrg(prev => prev || organizations[0].id);
    } catch(e) {if(active)setError(e instanceof Error ? e.message : "Authentication required");}})();
    return () => {active=false};
  },[]);
  useEffect(() => {if(org) void load(org)},[org,load]);
  async function mutate(path:string, method:string, data:unknown) {
    if (!session || !org) return;
    setBusy(true);setError("");setSuccess("");
    try {
      await api(path,{method,body:JSON.stringify(data)},session.csrf_token);
      setSuccess("Action saved. Check activity history below.");
      await load(org);
    } catch(e) {setError(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));}
    finally {setBusy(false)}
  }
  async function knowledgeSearch() {
    if (!base || query.trim().length < 3) return;
    setBusy(true);
    try {
      const r=await api<{citations:Evidence[]}>(`${base}/knowledge/search?q=${encodeURIComponent(query.trim())}`);
      setEvidence(r.citations);setError("");
    } catch(e) {setError(String(e));}finally{setBusy(false)}
  }
  const navigation=[['approvals','Approval Queue'],['planner','Agent Planner'],['tasks','Tasks'],['knowledge','Knowledge'],['activity','Activity & Delivery']];
  return <main className="min-h-screen bg-[#fffaf1] text-[#26211b]">
    <header className="border-b border-amber-200 bg-white px-4 py-5 shadow-sm md:px-10">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        <div><div className="text-xs font-bold uppercase tracking-[.25em] text-amber-700">Instant Mechanic Hire</div>
        <h1 className="text-2xl font-bold md:text-3xl">AI Recruitment Automation</h1>
        <p className="text-sm text-stone-600">Phase 6 | Human-approved agent workflows</p></div>
        <a href="/phase3" className="rounded-xl border border-amber-300 px-4 py-2 text-sm font-semibold">Recruitment Dashboard</a>
      </div>
    </header>
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-7 md:px-10">
      {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">{error} {!session && <a className="underline" href="/auth-live">Sign in</a>}</div>}
      {success && <div role="status" className="rounded-xl border border-green-300 bg-green-50 p-4 text-green-900">{success}</div>}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-white p-4">
        <label className="text-sm font-semibold">Organization <select aria-label="Organization" value={org} onChange={e=>setOrg(e.target.value)} className="ml-2 rounded-lg border border-amber-200 bg-white p-2">
          {orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
        </select></label>
        <button disabled={!org || busy} onClick={()=>void load(org)} className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white disabled:opacity-40">Refresh</button>
      </div>
      {!org && session && <p className="rounded-xl bg-amber-50 p-4">No organizations available. Create an organization in the Super Admin workspace first.</p>}
      <section className="grid gap-3 sm:grid-cols-3">
        {[["Proposed actions",overview?.total_proposals??"-"],["Pending approval",overview?.proposal_counts?.pending??0],["Open tasks",overview?.open_tasks??0]].map(([label,value])=><div key={String(label)} className="rounded-2xl border border-amber-200 bg-white p-5 shadow-sm"><p className="text-sm text-stone-500">{label}</p><p className="mt-2 text-3xl font-bold text-amber-700">{value}</p></div>)}
      </section>
      <nav className="flex flex-wrap gap-2" aria-label="Automation sections">{navigation.map(([id,label])=><button key={id} aria-pressed={tab===id} className={`rounded-xl px-4 py-2 text-sm font-semibold ${tab===id?"bg-amber-600 text-white":"border border-amber-200 bg-white"}`} onClick={()=>setTab(id)}>{label}</button>)}</nav>
      {tab==="approvals" && <section className="space-y-4">
        <h2 className="text-xl font-bold">Recruiter approval queue</h2>
        <p className="text-sm text-stone-600">Agent proposals cannot be sent without explicit approval and a separate queue action. Review all candidate information before approving.</p>
        {proposals.length===0 && <p className="rounded-xl bg-white p-5">No proposals yet. Use Agent Planner to draft an action.</p>}
        {proposals.map(p=><article key={p.id} className="space-y-3 rounded-2xl border border-amber-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold">{p.title}</h3><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase text-amber-900">{p.state}</span></div>
          <p className="text-xs text-stone-500">{p.kind.replaceAll("_"," ")}{p.last_error ? ` | ${p.last_error}` : ""}</p>
          <textarea aria-label={`Draft ${p.id}`} className="min-h-28 w-full rounded-xl border border-stone-200 bg-[#fffdf9] p-3 text-sm" value={editDraft[p.id]??p.draft} disabled={p.state!=="pending"} onChange={e=>setEditDraft(x=>({...x,[p.id]:e.target.value}))}/>
          <div className="flex flex-wrap gap-2">
            {p.state==="pending" && <><button disabled={busy} className="rounded-lg bg-green-700 px-4 py-2 text-sm font-bold text-white" onClick={()=>void mutate(`${base}/proposals/${p.id}/decision`,"POST",{decision:"approve",edited_draft:editDraft[p.id]??p.draft})}>Approve</button>
            <button disabled={busy} className="rounded-lg border border-red-400 px-4 py-2 text-sm font-semibold text-red-800" onClick={()=>void mutate(`${base}/proposals/${p.id}/decision`,"POST",{decision:"reject"})}>Reject</button></>}
            {p.state==="approved" && <button disabled={busy} className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-bold text-white" onClick={()=>void mutate(`${base}/proposals/${p.id}/queue`,"POST",{})}>Queue approved action</button>}
            {p.state==="pending" || p.state==="approved" || p.state==="queued" ? <button disabled={busy} className="rounded-lg border px-4 py-2 text-sm" onClick={()=>void mutate(`${base}/proposals/${p.id}/decision`,"POST",{decision:"cancel"})}>Cancel</button> : null}
          </div>
        </article>)}
      </section>}
      {tab==="planner" && <section className="rounded-2xl border border-amber-200 bg-white p-5 space-y-4">
        <h2 className="text-xl font-bold">Free AI action planner</h2>
        <p className="text-sm text-stone-600">Drafts approved templates using existing interview or application IDs. No paid model API required.</p>
        <div className="grid gap-3 md:grid-cols-2"><label className="text-sm font-semibold">Action type<select value={kind} onChange={e=>{setKind(e.target.value);if(e.target.value==="interview_reminder")setTargetType("interview")}} className="mt-1 block w-full rounded-lg border p-2">{["interview_reminder","interview_invitation","application_followup","document_request"].map(v=><option key={v} value={v}>{v.replaceAll("_"," ")}</option>)}</select></label>
        <label className="text-sm font-semibold">Target type<select value={targetType} onChange={e=>setTargetType(e.target.value)} className="mt-1 block w-full rounded-lg border p-2"><option value="interview">Interview</option><option value="application">Application</option></select></label></div>
        <label className="block text-sm font-semibold">Existing interview or application UUID<input value={targetId} onChange={e=>setTargetId(e.target.value)} placeholder="Paste record ID from your recruitment dashboard" className="mt-1 block w-full rounded-lg border p-3"/></label>
        <button disabled={!org||busy||!targetId} className="rounded-lg bg-amber-600 px-5 py-2 font-bold text-white disabled:opacity-40" onClick={()=>void mutate(`${base}/proposals`,"POST",{kind,target_type:targetType,target_id:targetId})}>Generate draft for approval</button>
      </section>}
      {tab==="tasks" && <section className="space-y-4 rounded-2xl border border-amber-200 bg-white p-5"><h2 className="text-xl font-bold">Recruiter tasks</h2><div className="flex flex-wrap gap-2"><input className="min-w-48 flex-1 rounded-lg border p-3" placeholder="New task title" value={taskTitle} onChange={e=>setTaskTitle(e.target.value)}/><button disabled={!taskTitle.trim()||busy} className="rounded-lg bg-amber-600 px-4 text-white disabled:opacity-40" onClick={async()=>{await mutate(`${base}/tasks`,"POST",{title:taskTitle});setTaskTitle("")}}>Add task</button></div>{tasks.map(t=><div key={t.id} className="flex flex-wrap items-center justify-between gap-2 border-b py-2"><span>{t.title} <small className="text-stone-500">({t.status})</small></span>{t.status==="open"&&<button disabled={busy} onClick={()=>void mutate(`${base}/tasks/${t.id}`,"PATCH",{status:"done"})} className="rounded-lg border px-3 py-1 text-sm">Mark done</button>}</div>)}</section>}
      {tab==="knowledge" && <section className="space-y-4 rounded-2xl border border-amber-200 bg-white p-5"><h2 className="text-xl font-bold">Recruitment knowledge assistant</h2><p className="text-sm text-stone-600">Stores approved company policies by organization. Search returns cited extracts only, not fabricated answers.</p>
        <div className="space-y-2"><input className="w-full rounded-lg border p-3" placeholder="Policy title" value={docTitle} onChange={e=>setDocTitle(e.target.value)}/><textarea className="min-h-24 w-full rounded-lg border p-3" placeholder="Paste an approved internal policy (no candidate private data)" value={docBody} onChange={e=>setDocBody(e.target.value)}/><button disabled={busy||docBody.length<20||docTitle.length<3} className="rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white disabled:opacity-40" onClick={async()=>{await mutate(`${base}/knowledge`,"POST",{title:docTitle,body:docBody});setDocTitle("");setDocBody("")}}>Save approved policy</button></div>
        <div className="flex flex-wrap gap-2"><input className="min-w-48 flex-1 rounded-lg border p-3" placeholder="Search policies with citations" value={query} onChange={e=>setQuery(e.target.value)}/><button disabled={busy||query.trim().length<3} onClick={()=>void knowledgeSearch()} className="rounded-lg border border-amber-500 px-4 py-2 font-semibold">Search</button></div>
        {evidence.length===0 && <p className="text-sm text-stone-500">No matching approved excerpts.</p>}
        {evidence.map(e=><div key={e.id} className="rounded-lg bg-amber-50 p-3"><strong>{e.title}</strong><p className="mt-1 whitespace-pre-line text-sm">{e.excerpt}</p><small>Source ID: {e.id}</small></div>)}
      </section>}
      {tab==="activity" && <section className="grid gap-5 md:grid-cols-2"><div className="rounded-2xl border border-amber-200 bg-white p-5"><h2 className="mb-3 text-xl font-bold">Audit events</h2>{events.length===0&&<p>No activity yet.</p>}{events.map(e=><div className="border-b py-2 text-sm" key={e.id}>{e.event}<div className="text-xs text-stone-500">{e.created_at}</div></div>)}</div><div className="rounded-2xl border border-amber-200 bg-white p-5"><h2 className="mb-3 text-xl font-bold">Delivery status</h2><p className="text-xs text-stone-500">Outbox means saved for review, NOT emailed to the candidate.</p>{deliveries.map(d=><div key={d.proposal_id} className="border-b py-2 text-sm">{d.status} | {d.mode}</div>)}</div></section>}
      <footer className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-stone-600">Agent outputs are advisory. Recruiters are responsible for verifying information and approving communications. No automatic hiring decisions. All actions are scoped to authorized organizations.</footer>
    </div>
  </main>;
}
