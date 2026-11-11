"use client";
import {useCallback,useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {api,encoded, type Session,type Organization,type Job,type Application,type Candidate,type Interview,type Category,type AdminUser,type ImportBatch,type AppSetting} from "../../lib/api/phase3";

type Section = "Overview"|"Jobs"|"Candidates"|"Applications"|"Interviews"|"Import"|"Super Admin";
type Stat = {jobs:number;applications:number;interviews:number};
type Audit = {action:string;created_at:string;context:Record<string,unknown>};
const sections:Section[]=["Overview","Jobs","Candidates","Applications","Interviews","Import","Super Admin"];
const shell:React.CSSProperties={background:"#fffaf2",minHeight:"100vh",color:"#211c17",fontFamily:"Arial, sans-serif"};
const btn:React.CSSProperties={background:"#ffbf25",color:"#211c17",padding:"11px 15px",border:"1px solid #eda819",borderRadius:9,fontWeight:700,cursor:"pointer"};
const input:React.CSSProperties={padding:"11px 12px",border:"1px solid #dfd5c7",borderRadius:8,width:"100%",background:"white",color:"#211c17"};
const panel:React.CSSProperties={padding:21,background:"white",border:"1px solid #ebe0d2",borderRadius:14};
const sub:React.CSSProperties={color:"#756b60",fontSize:13};
const field:React.CSSProperties={display:"grid",gap:5,fontSize:13,fontWeight:600};

export default function Phase3Workspace(){
 const router=useRouter();
 const [session,setSession]=useState<Session|null>(null);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const [section,setSection]=useState<Section>("Overview");
 const [organizations,setOrganizations]=useState<Organization[]>([]);
 const [org,setOrg]=useState("");
 const [categories,setCategories]=useState<Category[]>([]);
 const [jobs,setJobs]=useState<Job[]>([]);const [apps,setApps]=useState<Application[]>([]);
 const [candidates,setCandidates]=useState<Candidate[]>([]);const [interviews,setInterviews]=useState<Interview[]>([]);
 const [stats,setStats]=useState<Stat|null>(null);
 const [users,setUsers]=useState<AdminUser[]>([]);const [settings,setSettings]=useState<AppSetting[]>([]);const [audits,setAudits]=useState<Audit[]>([]);const [batches,setBatches]=useState<ImportBatch[]>([]);
 const [title,setTitle]=useState("");const [category,setCategory]=useState("");const [description,setDescription]=useState("");const [location,setLocation]=useState("");
 const [orgName,setOrgName]=useState("Instant Mechanic");const [orgSlug,setOrgSlug]=useState("instant-mechanic");
 const [memberEmail,setMemberEmail]=useState("");const [memberRole,setMemberRole]=useState("recruiter");
 const [settingKey,setSettingKey]=useState("recruitment_notice");const [settingValue,setSettingValue]=useState("");
 const [selectedFile,setSelectedFile]=useState<File|null>(null);const [preview,setPreview]=useState<{valid_count:number;errors:{row:number;errors:string[]}[];sample:unknown[]}|null>(null);
 const [appStage,setAppStage]=useState<Record<string,string>>({});const [interviewDate,setInterviewDate]=useState<Record<string,string>>({});
 const csrf=session?.csrf_token||"";const admin=!!session?.user.is_platform_admin;
 const recruiter=admin || !!session?.user.memberships.find(m=>m.organization_id===org && ["owner","admin","recruiter"].includes(m.role));
 const request=useCallback(async<T,>(path:string,options:RequestInit={})=>api<T>(path,options,csrf),[csrf]);
 const mutate=useCallback(async<T,>(path:string,method:string,data?:unknown)=>request<T>(path,{method,body:data===undefined?undefined:JSON.stringify(data)}),[request]);
 const refresh=useCallback(async()=>{
  const [os,cs]=await Promise.all([request<Organization[]>("/api/recruitment/organizations"),request<Category[]>("/api/recruitment/categories")]);
  setOrganizations(os);setCategories(cs);setOrg(current=>os.some(o=>o.id===current)?current:(os[0]?.id||""));
 },[request]);
 useEffect(()=>{let cancelled=false;
  api<Session>("/api/auth/me").then(s=>{if(!cancelled){setSession(s);setLoading(false);}}).catch(()=>{if(!cancelled)router.replace("/auth-live");});
  return()=>{cancelled=true};
 },[router]);
 useEffect(()=>{if(!session)return;refresh().catch(e=>setError(String(e)));},[session,refresh]);
 const load=useCallback(async()=>{
  if(!org)return;
  setError("");
  const base=`/api/recruitment/organizations/${encoded(org)}`;
  if(recruiter){
   try{
    const [js,as,cs,iv,st,im]=await Promise.all([request<Job[]>(`${base}/jobs`),request<Application[]>(`${base}/applications`),request<Candidate[]>(`${base}/candidates`),request<Interview[]>(`${base}/interviews`),request<Stat>(`${base}/analytics`),request<ImportBatch[]>(`/api/admin-v3/organizations/${encoded(org)}/imports`)]);
    setJobs(js);setApps(as);setCandidates(cs);setInterviews(iv);setStats(st);setBatches(im);
   }catch(e){setError(e instanceof Error?e.message:String(e));}
  }
  if(admin){
   try{const [us,se,au]=await Promise.all([request<AdminUser[]>("/api/admin-v3/users"),request<AppSetting[]>("/api/admin-v3/settings"),request<Audit[]>("/api/admin-v3/audit")]);setUsers(us);setSettings(se);setAudits(au);}catch(e){setError(String(e));}
  }
 },[org,admin,recruiter,request]);
 useEffect(()=>{if(session && org)load();},[session,org,load]);
 const act=async(action:()=>Promise<unknown>,message:string)=>{setError("");setNotice("");try{await action();setNotice(message);await load();}catch(e){setError(e instanceof Error?e.message:String(e));}};
 const orgBase=`/api/recruitment/organizations/${encoded(org)}`;
 const jobName=(id:string)=>jobs.find(j=>j.id===id)?.title||id.slice(0,8);
 if(loading)return <main style={{...shell,padding:40}}>Checking secure session…</main>;
 return <div style={shell}>
  <div style={{display:"flex",minHeight:"100vh",flexWrap:"wrap"}}>
   <aside style={{width:240,flex:"0 0 240px",background:"white",borderRight:"1px solid #ebe0d2",padding:"28px 19px"}}>
    <div style={{fontSize:23,fontWeight:800,marginBottom:5}}>Instant <span style={{color:"#e98512"}}>Mechanic</span></div>
    <div style={{...sub,marginBottom:26}}>HIRE · LIVE OPERATIONS</div>
    <div style={{display:"grid",gap:7}}>{sections.filter(s=>s!=="Super Admin"||admin).map(s=><button key={s} onClick={()=>setSection(s)} style={{textAlign:"left",border:0,borderRadius:9,padding:"12px 13px",background:section===s?"#ffbd26":"transparent",color:"#35281c",fontWeight:section===s?750:500,cursor:"pointer"}}>{s}</button>)}</div>
    <div style={{borderTop:"1px solid #eee4d8",marginTop:30,paddingTop:16,...sub}}>Authenticated as<br/><strong style={{color:"#211c17"}}>{session?.user.email}</strong><p>{admin?"Platform Admin":"Organization member"}</p></div>
    <a href="/auth-live/account" style={{color:"#995300"}}>Account & logout</a>
   </aside>
   <main style={{flex:"1 1 700px",minWidth:0,padding:"30px clamp(16px,4vw,45px)"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap",marginBottom:22}}><div><div style={sub}>PHASE 3 · DATABASE-BACKED</div><h1 style={{fontSize:30,margin:"6px 0"}}>{section}</h1><p style={sub}>Real PostgreSQL records · Human-controlled recruitment decisions</p></div><div style={{minWidth:230}}><label style={field}>Organization<select value={org} onChange={e=>setOrg(e.target.value)} style={input}><option value="">Select organization</option>{organizations.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div></div>
    {error&&<div role="alert" style={{padding:13,background:"#fff0ed",border:"1px solid #e7b2a8",borderRadius:8,color:"#ab2418",marginBottom:15}}>{error}</div>}
    {notice&&<div role="status" style={{padding:13,background:"#fff4d7",borderRadius:8,marginBottom:15}}>{notice}</div>}
    {!org && !admin && <div style={panel}>You are not a recruiter in any organization. A platform administrator can assign you to an organization.</div>}
    {!org && admin && <div style={panel}><h2>Create your first organization</h2><p style={sub}>Set up Instant Mechanic before creating vacancies.</p><div style={{display:"grid",gap:10,maxWidth:400}}><label style={field}>Name<input style={input} value={orgName} onChange={e=>setOrgName(e.target.value)}/></label><label style={field}>Slug<input style={input} value={orgSlug} onChange={e=>setOrgSlug(e.target.value)}/></label><button style={btn} onClick={()=>act(async()=>{await mutate('/api/recruitment/organizations','POST',{name:orgName,slug:orgSlug});await refresh();},'Organization created')}>Create organization</button></div></div>}
    {section==="Overview"&&org&&<div style={{display:"grid",gap:16}}><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(170px,1fr))",gap:14}}>{([['Active workspace',organizations.find(o=>o.id===org)?.name||'—'],['Jobs',stats?.jobs??'—'],['Applications',stats?.applications??'—'],['Interviews',stats?.interviews??'—']] as [string,string|number][]).map(([k,v])=><div style={panel} key={k}><div style={sub}>{k}</div><div style={{fontSize:28,fontWeight:800,marginTop:14}}>{v}</div></div>)}</div><div style={panel}><h2>Recent jobs</h2>{jobs.slice(0,8).map(j=><div key={j.id} style={{borderTop:"1px solid #eee",padding:"12px 0",display:"flex",justifyContent:"space-between",gap:10}}><strong>{j.title}</strong><span>{j.status}</span></div>)}{jobs.length===0&&<p style={sub}>No live vacancies yet.</p>}</div></div>}
    {section==="Jobs"&&org&&recruiter&&<div style={{display:"grid",gap:16}}><div style={panel}><h2 style={{marginTop:0}}>Create job vacancy</h2><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:12}}><label style={field}>Title<input style={input} value={title} onChange={e=>setTitle(e.target.value)}/></label><label style={field}>Official category<select style={input} value={category} onChange={e=>setCategory(e.target.value)}><option value="">Choose role</option>{categories.map(c=><option key={c.slug} value={c.slug}>{c.title}</option>)}</select></label><label style={field}>Location<input style={input} value={location} onChange={e=>setLocation(e.target.value)}/></label><label style={field}>Description<textarea style={input} value={description} onChange={e=>setDescription(e.target.value)}/></label></div><button style={{...btn,marginTop:14}} onClick={()=>act(async()=>{await mutate(`${orgBase}/jobs`,'POST',{title,category_slug:category,location,description,status:'draft'});setTitle('');setDescription('');},'Job saved as draft')}>Save draft vacancy</button></div><div style={panel}><h2>Live vacancies</h2>{jobs.length===0?<p style={sub}>No jobs created.</p>:jobs.map(j=><div key={j.id} style={{borderTop:"1px solid #eee",padding:"14px 0",display:"flex",gap:12,justifyContent:"space-between",flexWrap:"wrap"}}><div><strong>{j.title}</strong><div style={sub}>{j.category_slug} · {j.location||'Location not set'} · {j.status}</div></div><select value={j.status} style={{...input,width:165}} onChange={e=>act(()=>mutate(`${orgBase}/jobs/${encoded(j.id)}`,'PATCH',{status:e.target.value}),`Job status updated to ${e.target.value}`)}>{['draft','published','paused','closed'].map(v=><option key={v}>{v}</option>)}</select></div>)}</div></div>}
    {section==="Candidates"&&org&&recruiter&&<div style={panel}><h2>Applicants</h2>{candidates.length===0?<p style={sub}>Candidates appear after they apply to an organization job.</p>:candidates.map(c=><div key={c.id} style={{padding:"13px 0",borderTop:"1px solid #eee"}}><strong>{c.full_name}</strong><p style={sub}>{c.email} · {c.city||'City not provided'}</p><p style={sub}>Skills: {Object.keys(c.skills||{}).join(', ')||'Not provided'}</p></div>)}</div>}
    {section==="Applications"&&org&&recruiter&&<div style={panel}><h2>Hiring pipeline</h2>{apps.length===0?<p style={sub}>No submitted applications yet.</p>:apps.map(a=><div key={a.id} style={{display:"flex",justifyContent:"space-between",gap:14,flexWrap:"wrap",padding:"13px 0",borderTop:"1px solid #eee"}}><div><strong>{jobName(a.job_id)}</strong><p style={sub}>Candidate {a.candidate_id.slice(0,8)} · Stage: {a.stage}</p></div><div style={{display:"flex",gap:7}}><select style={{...input,width:165}} value={appStage[a.id]||a.stage} onChange={e=>setAppStage(v=>({...v,[a.id]:e.target.value}))}>{['applied','screening','shortlisted','trade_test','interview','offer','hired','rejected','withdrawn'].map(s=><option key={s}>{s}</option>)}</select><button style={btn} onClick={()=>act(()=>mutate(`${orgBase}/applications/${encoded(a.id)}/stage`,'PATCH',{stage:appStage[a.id]||a.stage,note:'Updated by a recruiter in the Phase 3 workspace'}),'Stage recorded')}>Save</button></div></div>)}</div>}
    {section==="Interviews"&&org&&recruiter&&<div style={{display:"grid",gap:16}}><div style={panel}><h2>Schedule an interview</h2>{apps.length===0?<p style={sub}>Applications must exist before interviews can be scheduled.</p>:apps.map(a=><div key={a.id} style={{display:"flex",gap:10,padding:"10px 0",alignItems:"end",flexWrap:"wrap",borderTop:"1px solid #eee"}}><div style={{flex:1,minWidth:180}}><strong>{jobName(a.job_id)}</strong><p style={sub}>Candidate {a.candidate_id.slice(0,8)}</p></div><label style={field}>Date/time<input type="datetime-local" style={{...input,width:200}} value={interviewDate[a.id]||''} onChange={e=>setInterviewDate(v=>({...v,[a.id]:e.target.value}))}/></label><button style={btn} disabled={!interviewDate[a.id]} onClick={()=>act(()=>mutate(`${orgBase}/interviews`,'POST',{application_id:a.id,scheduled_at:new Date(interviewDate[a.id]).toISOString()}),'Interview scheduled')}>Schedule</button></div>)}</div><div style={panel}><h2>Upcoming and completed</h2>{interviews.length===0?<p style={sub}>No interviews yet.</p>:interviews.map(i=><div key={i.id} style={{borderTop:"1px solid #eee",padding:12,display:"flex",justifyContent:"space-between",flexWrap:"wrap",gap:10}}><div>{i.scheduled_at?new Date(i.scheduled_at).toLocaleString():"Time not set"}<p style={sub}>Application {i.application_id.slice(0,8)}</p></div><select style={{...input,width:175}} value={i.status} onChange={e=>act(()=>mutate(`${orgBase}/interviews/${encoded(i.id)}`,'PATCH',{status:e.target.value}),'Interview status updated')}>{['scheduled','in_progress','completed','cancelled','no_show'].map(v=><option key={v}>{v}</option>)}</select></div>)}</div></div>}
    {section==="Import"&&org&&recruiter&&<div style={{display:"grid",gap:16}}><div style={panel}><h2>CSV / Excel jobs import</h2><p style={sub}>Required columns: title, category_slug. Optional: description, location. Review errors before committing. Imports always create drafts.</p><input type="file" accept=".csv,.xlsx" onChange={e=>{setSelectedFile(e.target.files?.[0]||null);setPreview(null);}}/><div style={{display:"flex",gap:10,marginTop:18,flexWrap:"wrap"}}><button style={btn} disabled={!selectedFile} onClick={()=>act(async()=>{const data=new FormData();if(selectedFile)data.append('file',selectedFile);setPreview(await request(`${'/api/admin-v3/organizations'}/${encoded(org)}/imports/preview`,{method:'POST',body:data}));},'Preview ready')}>Preview file</button><button style={btn} disabled={!selectedFile||!preview||preview.errors.length>0||preview.valid_count===0} onClick={()=>act(async()=>{const data=new FormData();if(selectedFile)data.append('file',selectedFile);await request(`/api/admin-v3/organizations/${encoded(org)}/imports/commit`,{method:'POST',body:data});setPreview(null);},'Draft jobs imported')}>Import valid rows</button></div>{preview&&<div style={{marginTop:15}}><p>Valid rows: <strong>{preview.valid_count}</strong>; errors: <strong>{preview.errors.length}</strong></p>{preview.errors.map(e=><p key={e.row} style={{color:'#b42318'}}>Row {e.row}: {e.errors.join('; ')}</p>)}</div>}</div><div style={panel}><h2>Import history & undo</h2>{batches.map(b=><div key={b.id} style={{display:"flex",justifyContent:"space-between",gap:10,padding:"12px 0",borderTop:"1px solid #eee"}}><span>{b.filename} — {b.status}</span>{b.status==='applied'&&<button style={btn} onClick={()=>act(()=>mutate(`/api/admin-v3/organizations/${encoded(org)}/imports/${encoded(b.id)}/undo`,'POST'),'Import undone')}>Undo</button>}</div>)}{batches.length===0&&<p style={sub}>No imports yet.</p>}</div></div>}
    {section==="Super Admin"&&admin&&<div style={{display:"grid",gap:16}}><div style={panel}><h2>User management</h2><p style={sub}>Only platform administrators can assign organization roles.</p><div style={{display:"flex",gap:10,alignItems:"end",flexWrap:"wrap"}}><label style={{...field,flex:1,minWidth:200}}>Registered user email<input style={input} value={memberEmail} onChange={e=>setMemberEmail(e.target.value)}/></label><label style={field}>Role<select style={input} value={memberRole} onChange={e=>setMemberRole(e.target.value)}>{['recruiter','admin','owner','interviewer','candidate'].map(r=><option key={r}>{r}</option>)}</select></label><button style={btn} disabled={!org} onClick={()=>act(()=>mutate('/api/admin-v3/memberships','POST',{email:memberEmail,organization_id:org,role:memberRole}),'Organization role saved')}>Assign role</button></div>{users.map(u=><p key={u.id} style={{padding:"9px 0",borderBottom:"1px solid #eee"}}><strong>{u.full_name}</strong> · {u.email} {u.is_platform_admin?'· Platform admin':''}</p>)}</div><div style={panel}><h2>Application settings</h2><div style={{display:"flex",gap:10,flexWrap:"wrap",alignItems:"end"}}><label style={{...field,flex:1,minWidth:170}}>Key<input style={input} value={settingKey} onChange={e=>setSettingKey(e.target.value)}/></label><label style={{...field,flex:1,minWidth:170}}>Value<input style={input} value={settingValue} onChange={e=>setSettingValue(e.target.value)}/></label><button style={btn} onClick={()=>act(()=>mutate(`/api/admin-v3/settings/${encoded(settingKey)}`,'PUT',{value:settingValue}),'Setting saved')}>Save</button></div>{settings.map(s=><p key={s.key}><strong>{s.key}</strong>: {JSON.stringify(s.value)}</p>)}</div><div style={panel}><h2>Recent audit log</h2>{audits.map((a,i)=><p key={i} style={{borderTop:"1px solid #eee",padding:"8px 0"}}><strong>{a.action}</strong> · {a.created_at}</p>)}</div></div>}
    {!recruiter&&org&&section!=="Super Admin"&&<div style={panel}>This section requires an organization recruiter or administrator role. Unauthorized requests are also blocked by FastAPI.</div>}
    <div style={{...sub,marginTop:25}}>No automated candidate rejection or hiring decisions. All stage changes require an authorized person.</div>
   </main>
  </div>
 </div>;
}
