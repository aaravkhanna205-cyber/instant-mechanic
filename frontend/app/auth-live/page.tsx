"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function LiveSignIn() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) { setError(res.status === 429 ? "Too many attempts. Please try later." : "Sign-in failed. Check your credentials and backend connection."); return; }
      router.replace("/auth-live/account");
    } catch { setError("Cannot reach the authentication API. Check that FastAPI is running and CORS allows this frontend origin."); }
    finally { setBusy(false); }
  }
  return <main style={{ minHeight:"100vh",display:"grid",placeItems:"center",background:"#fffbf5",padding:24 }}>
    <form onSubmit={signIn} style={{ width:"100%",maxWidth:440,border:"1px solid #f1e4d2",borderRadius:16,background:"white",padding:36,boxShadow:"0 12px 36px #2414000c" }}>
      <h1 style={{ fontSize:24,fontWeight:750,marginBottom:12 }}>Instant Mechanic Hire</h1>
      <h2 style={{ fontSize:20,marginBottom:10 }}>Secure sign in</h2>
      <p style={{ color:"#6b625a",marginBottom:25 }}>Phase 3 authentication · PostgreSQL + Redis</p>
      <label htmlFor="email" style={{ display:"block",marginBottom:8 }}>Email</label>
      <input id="email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} style={{ width:"100%",padding:12,border:"1px solid #cabdab",borderRadius:8,marginBottom:18 }} />
      <label htmlFor="password" style={{ display:"block",marginBottom:8 }}>Password</label>
      <input id="password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} style={{ width:"100%",padding:12,border:"1px solid #cabdab",borderRadius:8,marginBottom:18 }} />
      {error && <p role="alert" style={{ color:"#b42318",marginBottom:16 }}>{error}</p>}
      <button type="submit" disabled={busy} style={{ width:"100%",padding:14,background:"#ffbd26",border:0,borderRadius:8,fontWeight:700,cursor:"pointer" }}>{busy ? "Signing in…" : "Sign in"}</button>
      <p style={{ marginTop:20,color:"#6b625a",fontSize:12 }}>Use your bootstrapped administrator account. No demo credentials.</p>
    </form>
  </main>;
}
