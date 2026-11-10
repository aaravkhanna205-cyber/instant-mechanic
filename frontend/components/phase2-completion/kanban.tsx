"use client";
import Link from "next/link";
import {useParams} from "next/navigation";
import {useState} from "react";
import {HIRING_STAGES,Stage,useDemo} from "@/lib/demo/store";
import {DemoNotice,Empty,PageTitle,Pill} from "@/components/phase2/common";

export function HiringKanban(){
  const {data,update}=useDemo();const params=useParams();const [notice,setNotice]=useState("");const [dragging,setDragging]=useState<string|null>(null);const [filter,setFilter]=useState("");
  const job=data.jobs.find(j=>j.id===params.id);
  if(!job)return <Empty text="This job was not found in your demo workspace."/>;
  const applications=data.applications.filter(a=>a.jobId===job.id).filter(a=>{const c=data.candidates.find(c=>c.id===a.candidateId);return (c?.name||"").toLowerCase().includes(filter.toLowerCase())});
  function move(id:string,stage:Stage){if(!job)return;const current=data.applications.find(a=>a.id===id);if(!current||current.jobId!==job.id||current.stage===stage)return;update(s=>({...s,applications:s.applications.map(a=>a.id===id?{...a,stage}:a)}),`Human moved application ${id}: ${current.stage} to ${stage}`);setNotice(`Moved candidate from ${current.stage} to ${stage} (demo).`);setDragging(null)}
  return <><PageTitle title={job.title} subtitle={`${job.department} · ${job.location} · ${job.type}`} action={<Link className="btn btn-primary" href={`/jobs/${job.id}/edit`}>Edit job</Link>}/><DemoNotice/>
   <section className="panel p-5 mb-5"><div className="flex flex-wrap gap-2 mb-3"><Pill>{job.status}</Pill>{job.skills.map(s=><Pill key={s}>{s}</Pill>)}</div><p className="whitespace-pre-wrap">{job.description}</p><div className="mt-4 flex flex-wrap gap-2"><button className="btn" type="button" onClick={()=>update(s=>({...s,jobs:s.jobs.map(j=>j.id===job.id?{...j,status:j.status==="Published"?"Closed":"Published"}:j)}),`Human changed posting status: ${job.title}`)}> {job.status==="Published"?"Close posting":"Publish posting"}</button><Link className="btn" href="/jobs">Back to all jobs</Link></div></section>
   <div className="flex flex-wrap items-center justify-between gap-3 mb-3"><h2 className="section-title">Hiring Kanban · {applications.length} applications</h2><input aria-label="Filter applicants" placeholder="Filter applicants" className="control" value={filter} onChange={e=>setFilter(e.target.value)}/></div>
   <p className="text-muted text-xs mb-3">Drag a card to another stage or use the accessible stage selector. Every change requires a recruiter action; no automatic rejection.</p>
   {notice&&<p role="status" className="demo-note">{notice}</p>}
   <div className="board" aria-label="Hiring pipeline">{HIRING_STAGES.map(stage=><section key={stage} className="board-column" aria-label={`${stage} stage`} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect="move"}} onDrop={e=>{e.preventDefault();const id=e.dataTransfer.getData("text/plain")||dragging;if(id)move(id,stage)}}><h3 className="font-semibold text-sm">{stage} <span className="text-muted">({applications.filter(a=>a.stage===stage).length})</span></h3>{applications.filter(a=>a.stage===stage).map(a=>{const c=data.candidates.find(c=>c.id===a.candidateId);return <article key={a.id} draggable onDragStart={e=>{e.dataTransfer.setData("text/plain",a.id);e.dataTransfer.effectAllowed="move";setDragging(a.id)}} onDragEnd={()=>setDragging(null)} className={`board-card ${dragging===a.id?"opacity-60":""}`}><Link className="font-semibold underline" href={`/candidates/${a.candidateId}`}>{c?.name||"Candidate"}</Link><p className="text-muted text-xs mt-1">{c?.experience||"Review needed"}</p>{stage==="Trade test"&&<p className="text-xs mt-2">Workshop lead should record practical notes during review.</p>}<label className="block text-xs mt-3">Move to stage<select aria-label={`Stage for ${c?.name||a.id}`} value={a.stage} className="control w-full mt-1" onChange={e=>move(a.id,e.target.value as Stage)}>{HIRING_STAGES.map(s=><option key={s}>{s}</option>)}</select></label></article>})}</section>)}</div>
   {applications.length===0&&<Empty text="No matching applicants for this job. Try a different filter."/>}</>
}
