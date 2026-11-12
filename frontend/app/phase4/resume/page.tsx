"use client";
import {useEffect,useState} from "react";
import {api,API_URL,type Session} from "../../../lib/api/phase3";
type Doc={id:string;filename:string;status:string;skills:{skill:string;evidence:string}[];error:string|null};
export default function ResumeUpload(){
 const [session,setSession]=useState<Session|null>(null);const [docs,setDocs]=useState<Doc[]>([]);
 const [file,setFile]=useState<File|null>(null);const [consent,setConsent]=useState(false);const [status,setStatus]=useState("");
 async function refresh(){try{setDocs(await api<Doc[]>("/api/phase4/resumes/mine"));}catch(e){setStatus(e instanceof Error?e.message:String(e));}}
 useEffect(()=>{api<Session>("/api/auth/me").then(s=>{setSession(s);return api<Doc[]>("/api/phase4/resumes/mine")}).then(setDocs).catch(e=>setStatus(e.message));},[]);
 async function submit(e:React.FormEvent){e.preventDefault();if(!file||!consent||!session)return;setStatus("Uploading...");
 const body=new FormData();body.set("file",file);body.set("consent","true");
 try{const response=await fetch(`${API_URL}/api/phase4/resumes`,{method:"POST",credentials:"include",headers:{"X-CSRF-Token":session.csrf_token},body});
 const data=await response.json();if(!response.ok)throw Error(JSON.stringify(data.detail));setStatus("Queued. Start the Phase 4 worker, then refresh the list.");await refresh();}
 catch(e){setStatus(e instanceof Error?e.message:String(e));}}
 async function remove(id:string){if(!session||!window.confirm("Delete this resume and its extracted records?"))return;try{await api(`/api/phase4/resumes/${id}`,{method:"DELETE"},session.csrf_token);await refresh();}catch(e){setStatus(e instanceof Error?e.message:String(e));}}
 const panel:React.CSSProperties={background:"white",border:"1px solid #e5ded3",borderRadius:14,padding:22,margin:"18px 0"};
 return <main style={{background:"#fdf9f2",padding:"48px 5%",minHeight:"100vh"}}><h1>Candidate Resume — Phase 4</h1>
 <p>Upload your own PDF or DOCX resume for recruiter-reviewed evidence extraction. This is not an automatic hiring decision.</p>
 {!session&&<p>Please <a href="/auth-live">sign in</a> first.</p>}
 <form onSubmit={submit} style={panel}><label>Resume (PDF/DOCX, maximum 8 MB)<input type="file" accept=".pdf,.docx" required onChange={e=>setFile(e.target.files?.[0]||null)} style={{display:"block",marginTop:12}}/></label>
 <label style={{display:"block",marginTop:18}}><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to extraction and recruiter review for the jobs I apply to.</label>
 <button type="submit" disabled={!session||!file||!consent} style={{background:"#ffbc22",border:0,borderRadius:8,padding:12,marginTop:20}}>Upload privately</button></form>
 <p role="status">{status}</p>
 <section style={panel}><h2>My uploaded resumes</h2><button onClick={refresh}>Refresh status</button>
 {docs.map(d=><article key={d.id} style={{borderTop:"1px solid #eee",padding:12}}><strong>{d.filename}</strong> — {d.status}<p>{d.error}</p><p>{(d.skills||[]).map(s=>s.skill).join(", ")}</p><button onClick={()=>remove(d.id)}>Delete and withdraw this resume</button></article>)}
 {!docs.length&&<p>No resume uploads found.</p>}</section><a href="/phase4">Recruiter workspace</a></main>;
}
