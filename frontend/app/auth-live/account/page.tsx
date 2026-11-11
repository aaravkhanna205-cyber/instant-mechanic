"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
type Person = { email:string; full_name:string; is_platform_admin:boolean; memberships:{organization_id:string;role:string}[] };
export default function AccountPage() {
  const router = useRouter();
  const [person,setPerson] = useState<Person|null>(null);
  const [csrf,setCsrf] = useState("");
  const [error,setError] = useState("");
  useEffect(()=>{
    let alive = true;
    fetch(`${API}/api/auth/me`,{credentials:"include"}).then(async res=>{
      if(res.status===401){router.replace("/auth-live");return;}
      if(!res.ok) throw new Error("Unable to load account");
      const result = await res.json(); if(alive){setPerson(result.user);setCsrf(result.csrf_token);}
    }).catch(()=>{if(alive)setError("Unable to reach authenticated API");});
    return ()=>{alive=false;};
  },[router]);
  async function logout(){
    try {
      const res = await fetch(`${API}/api/auth/logout`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:"{}"});
      if(!res.ok) throw new Error("Logout failed");
      router.replace("/auth-live");
    } catch {setError("Logout could not be completed. Please try again.");}
  }
  return <main style={{background:"#fffbf5",minHeight:"100vh",padding:36}}><section style={{maxWidth:650,margin:"60px auto",background:"white",border:"1px solid #f1e4d2",borderRadius:14,padding:32}}>
    <h1 style={{fontSize:26,fontWeight:750}}>Instant Mechanic Hire — Account</h1>
    {error && <p role="alert" style={{color:"#b42318"}}>{error}</p>}
    {!person ? <p>Checking session…</p> : <><p style={{marginTop:20}}>Signed in as <strong>{person.full_name}</strong> ({person.email})</p>
    <p>Platform administrator: <strong>{person.is_platform_admin ? "Yes":"No"}</strong></p>
    <p>Organization roles: {person.memberships.length ? person.memberships.map(m=>m.role).join(", ") : "None"}</p>
    <button onClick={logout} style={{marginTop:22,padding:"12px 22px",border:0,borderRadius:8,background:"#ffbd26",cursor:"pointer"}}>Sign out</button></>}
  </section></main>;
}
