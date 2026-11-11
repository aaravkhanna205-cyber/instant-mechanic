"use client";
import {useCallback,useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {api,type Session,type Job,type Application} from "../../../lib/api/phase3";
const style={background:"#fffaf2",color:"#241d13",minHeight:"100vh",padding:"35px clamp(15px,5vw,60px)",fontFamily:"Arial,sans-serif"};
const card={padding:22,background:"white",border:"1px solid #e7dece",borderRadius:12,marginBottom:16};
const input={padding:12,border:"1px solid #ddd3c5",borderRadius:8,width:"100%"};
const button={background:"#ffbe24",padding:"11px 16px",border:0,borderRadius:9,fontWeight:700 as const,cursor:"pointer"};
export default function CandidatePortal(){
 const router=useRouter();const [session,setSession]=useState<Session|null>(null);
 const [jobs,setJobs]=useState<Job[]>([]);const [apps,setApps]=useState<Application[]>([]);
 const [city,setCity]=useState("");const [phone,setPhone]=useState("");const [skills,setSkills]=useState("");const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const refresh=useCallback(async()=>{const [js,as]=await Promise.all([api<Job[]>("/api/recruitment/public/jobs"),api<Application[]>("/api/recruitment/me/applications")]);setJobs(js);setApps(as);},[]);
 useEffect(()=>{api<Session>("/api/auth/me").then(s=>{setSession(s);return refresh();}).catch(()=>router.replace("/auth-live"));},[refresh,router]);
 const act=async (work:()=>Promise<unknown>,msg:string)=>{setError("");setNotice("");try{await work();setNotice(msg);await refresh();}catch(e){setError(e instanceof Error?e.message:String(e));}};
 return <main style={style}><header style={{display:"flex",justifyContent:"space-between",gap:20,flexWrap:"wrap"}}><div><h1>Instant Mechanic <span style={{color:'#ed8a0f'}}>Hire</span></h1><p>Candidate portal · real applications</p></div><a href="/auth-live/account">Account & logout</a></header>
 {error&&<p role="alert" style={{color:"#b42318"}}>{error}</p>}{notice&&<p role="status" style={{background:'#fff1cc',padding:10}}>{notice}</p>}
 <section style={card}><h2>My candidate profile</h2><p>Signed in: {session?.user.email||"Checking session…"}</p><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:10}}><label>City<input style={input} value={city} onChange={e=>setCity(e.target.value)}/></label><label>Phone<input style={input} value={phone} onChange={e=>setPhone(e.target.value)}/></label><label>Skills, separated by commas<input style={input} value={skills} onChange={e=>setSkills(e.target.value)}/></label></div><button style={{...button,marginTop:12}} disabled={!session} onClick={()=>act(()=>api('/api/recruitment/me/candidate-profile',{method:'PUT',headers:{'X-CSRF-Token':session?.csrf_token||''},body:JSON.stringify({city,phone,skills:Object.fromEntries(skills.split(',').map(s=>s.trim()).filter(Boolean).map(s=>[s,true]))})}),'Candidate profile saved')}>Save profile</button></section>
 <section style={card}><h2>Available vacancies</h2>{jobs.length===0&&<p>No published vacancies yet.</p>}{jobs.map(j=><div key={j.id} style={{padding:'15px 0',borderTop:'1px solid #eee',display:'flex',gap:10,justifyContent:'space-between',flexWrap:'wrap'}}><div><strong>{j.title}</strong><p style={{fontSize:13,color:'#665e55'}}>{j.location||'Location unspecified'} · {j.category_slug}</p><p>{j.description}</p></div><button style={button} disabled={apps.some(a=>a.job_id===j.id)} onClick={()=>act(()=>api(`/api/recruitment/jobs/${encodeURIComponent(j.id)}/apply`,{method:'POST',headers:{'X-CSRF-Token':session?.csrf_token||''}}),'Application submitted')}>{apps.some(a=>a.job_id===j.id)?'Applied':'Apply'}</button></div>)}</section>
 <section style={card}><h2>Application tracker</h2>{apps.length===0?<p>No applications yet.</p>:apps.map(a=><p key={a.id} style={{borderTop:'1px solid #eee',paddingTop:12}}>{jobs.find(j=>j.id===a.job_id)?.title||a.job_id.slice(0,8)} · <strong>{a.stage}</strong></p>)}</section><p style={{fontSize:12}}>Applications are not automatically evaluated or rejected. A recruiter reviews every decision.</p></main>;
}
