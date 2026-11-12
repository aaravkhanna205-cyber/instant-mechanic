"use client";
import {useEffect,useState} from "react";
import {api, type Organization, type Job, type Application, type Session} from "../../lib/api/phase3";

type Evidence={status:string;requirements:string[];evidence:string[];skills_to_verify?:{skill:string;evidence:string}[];disclaimer?:string};
export default function Phase4Recruiter(){
 const [session,setSession]=useState<Session|null>(null);
 const [orgs,setOrgs]=useState<Organization[]>([]);
 const [org,setOrg]=useState("");
 const [jobs,setJobs]=useState<Job[]>([]);
 const [job,setJob]=useState("");
 const [apps,setApps]=useState<Application[]>([]);
 const [appId,setAppId]=useState("");
 const [result,setResult]=useState<Evidence|null>(null);
 const [questions,setQuestions]=useState<string[]>([]);
 const [note,setNote]=useState("");
 const [message,setMessage]=useState("");
 useEffect(()=>{api<Session>("/api/auth/me").then(s=>{setSession(s);return api<Organization[]>("/api/recruitment/organizations")}).then(setOrgs).catch(e=>setMessage(e.message));},[]);
 useEffect(()=>{if(!org)return;api<Job[]>(`/api/recruitment/organizations/${encodeURIComponent(org)}/jobs`).then(setJobs).catch(e=>setMessage(e.message))},[org]);
 useEffect(()=>{if(!org||!job)return;
 // Recruitment API returns applications scoped by organization; filter client-side for selected job.
 api<Application[]>(`/api/recruitment/organizations/${encodeURIComponent(org)}/applications`).then(a=>setApps(a.filter(x=>x.job_id===job))).catch(e=>setMessage(e.message));},[org,job]);
 async function analyze(){if(!org||!appId)return;setMessage("Loading evidence...");try{const x=await api<Evidence>(`/api/phase4/organizations/${org}/applications/${appId}/evidence`);setResult(x);setMessage("");}catch(e){setMessage(e instanceof Error?e.message:String(e));}}
 async function getQuestions(){if(!org||!job)return;try{const x=await api<{questions:string[]}>(`/api/phase4/organizations/${org}/jobs/${job}/interview-questions`);setQuestions(x.questions);}catch(e){setMessage(e instanceof Error?e.message:String(e));}}
 async function saveReview(){if(!session||!org||!appId)return;try{await api(`/api/phase4/organizations/${org}/applications/${appId}/reviews`,{method:"POST",body:JSON.stringify({note})},session.csrf_token);setMessage("Human review saved. No application stage was changed.");setNote("");}catch(e){setMessage(e instanceof Error?e.message:String(e));}}
 const panel:React.CSSProperties={background:"white",border:"1px solid #e8e1d7",borderRadius:14,padding:22,marginBottom:18};
 const select:React.CSSProperties={padding:12,width:"100%",border:"1px solid #ccc",borderRadius:8,marginTop:8};
 const button:React.CSSProperties={padding:"12px 18px",background:"#ffbd22",border:0,borderRadius:9,cursor:"pointer",fontWeight:600,marginTop:12};
 return <main style={{background:"#fdf9f2",minHeight:"100vh",padding:"48px 5%",color:"#171717"}}>
 <h1>Instant Mechanic Hire — Phase 4 AI Assistance</h1><p>Evidence retrieval and interview prompts. All recruitment decisions remain with authorized people.</p>
 {!session&&<p role="alert">Sign in as an authorized recruiter at <a href="/auth-live">Secure login</a>.</p>}
 {message&&<p role="status" style={{color:"#9e3b17"}}>{message}</p>}
 <section style={panel}><label>Organization<select style={select} value={org} onChange={e=>{setOrg(e.target.value);setJobs([]);setApps([]);setJob("");setAppId("");setResult(null);}}><option value="">Choose an organization</option>{orgs.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
 <label>Job<select style={select} value={job} onChange={e=>{setJob(e.target.value);setApps([]);setAppId("");setResult(null);}}><option value="">Choose a job</option>{jobs.map(j=><option key={j.id} value={j.id}>{j.title}</option>)}</select></label>
 <label>Application<select style={select} value={appId} onChange={e=>setAppId(e.target.value)}><option value="">Choose an application</option>{apps.map(a=><option key={a.id} value={a.id}>{a.id.slice(0,8)} — {a.stage}</option>)}</select></label>
 <button style={button} disabled={!appId} onClick={analyze}>Retrieve resume evidence</button> <button style={button} disabled={!job} onClick={getQuestions}>Interview questions</button></section>
 {result&&<section style={panel}><h2>Resume evidence</h2><p>Status: {result.status}</p><p>Job requirements: {result.requirements.join(", ")||"Not specified"}</p>
 <h3>Relevant excerpts — candidate claims, not verified facts</h3>{result.evidence.length?result.evidence.map((e,i)=><p key={i} style={{padding:12,background:"#fff7e8"}}>{e}</p>):<p>No processed resume excerpts yet.</p>}
 <p>{result.disclaimer}</p></section>}
 {questions.length>0&&<section style={panel}><h2>Suggested interview questions</h2><ol>{questions.map((q,i)=><li key={i} style={{marginBottom:10}}>{q}</li>)}</ol><small>Questions require recruiter review; do not ask about protected characteristics.</small></section>}
 {appId&&<section style={panel}><h2>Human review note</h2><textarea style={{...select,minHeight:100}} maxLength={2000} value={note} onChange={e=>setNote(e.target.value)} placeholder="Evidence checked, uncertainties, follow-up steps..."/>
 <button style={button} onClick={saveReview} disabled={note.trim().length<4}>Save review note</button></section>}
 <p><a href="/phase3">Back to recruitment</a> · <a href="/phase4/resume">Candidate resume upload</a></p>
 </main>;
}
