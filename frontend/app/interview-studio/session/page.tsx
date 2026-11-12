"use client";
import { useEffect, useState } from "react";
import { api, type Session } from "../../../lib/api/phase3";

type MyInterview = {
  id: string; job_title: string; status: string; scheduled_at: string | null; timezone: string;
  duration_minutes: number; meeting_url: string | null; candidate_response: string;
  questions_total: number; questions_answered: number; consent_given: boolean;
};
type State = {
  interview_id: string; status: string; total: number; answered: number; all_answered: boolean;
  current: { id: string; position: number; text: string } | null;
};

const panel: React.CSSProperties = { background: "white", border: "1px solid #e5ded3", borderRadius: 14, padding: 22, margin: "18px 0" };
const primary: React.CSSProperties = { padding: "10px 16px", background: "#ffbc22", border: 0, borderRadius: 9, cursor: "pointer", fontWeight: 600, marginTop: 12, marginRight: 8 };
const plain: React.CSSProperties = { ...primary, background: "white", border: "1px solid #d8cfc0" };

function fail(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function CandidateInterview() {
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<MyInterview[]>([]);
  const [state, setState] = useState<State | null>(null);
  const [answer, setAnswer] = useState("");
  const [agree, setAgree] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Session>("/api/auth/me")
      .then((s) => { setSession(s); return api<MyInterview[]>("/api/interview-studio/me/interviews"); })
      .then(setItems)
      .catch((e) => setMessage(fail(e)));
  }, []);

  const mine = (id: string) => `/api/interview-studio/me/interviews/${encodeURIComponent(id)}`;

  async function run(action: () => Promise<void>, done: string) {
    if (!session) return;
    setBusy(true); setMessage("Working...");
    try { await action(); setMessage(done); } catch (e) { setMessage(fail(e)); } finally { setBusy(false); }
  }
  const reload = async () => setItems(await api<MyInterview[]>("/api/interview-studio/me/interviews"));

  const respond = (id: string, response: string) => run(async () => {
    await api(`${mine(id)}/respond`, { method: "POST", body: JSON.stringify({ response }) }, session!.csrf_token);
    await reload();
  }, response === "confirmed" ? "Thank you. Your interview is confirmed." : "You have declined this interview.");

  const consent = (id: string, granted: boolean) => run(async () => {
    await api(`${mine(id)}/consent`, { method: "POST", body: JSON.stringify({ granted }) }, session!.csrf_token);
    await reload();
  }, granted ? "Consent recorded. You can start when you are ready." : "Consent withdrawn.");

  const start = (id: string) => run(async () => { setAnswer(""); setState(await api<State>(`${mine(id)}/session`)); }, "");

  const save = () => run(async () => {
    if (!state?.current) return;
    const next = await api<State>(`${mine(state.interview_id)}/session/answers`,
      { method: "POST", body: JSON.stringify({ question_id: state.current.id, answer }) }, session!.csrf_token);
    setState(next); setAnswer("");
  }, "Answer saved.");

  const finish = () => run(async () => {
    if (!state) return;
    await api(`${mine(state.interview_id)}/session/complete`, { method: "POST" }, session!.csrf_token);
    setState(null); await reload();
  }, "Interview finished. Thank you. A recruiter will read your answers.");

  return (
    <main style={{ background: "#fdf9f2", padding: "48px 5%", minHeight: "100vh", color: "#171717" }}>
      <h1>My interviews</h1>
      {!session && <p>Please <a href="/auth-live">sign in</a> first.</p>}
      <p role="status" style={{ minHeight: 24, color: "#8a4b00" }}>{message}</p>

      {state ? (
        <section style={panel}>
          <p>Question {state.current ? state.current.position : state.total} of {state.total} · {state.answered} saved</p>
          {state.current ? (
            <>
              <h2 style={{ lineHeight: 1.35 }}>{state.current.text}</h2>
              <textarea rows={8} maxLength={6000} value={answer} onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer here. Use a real example where you can."
                style={{ width: "100%", padding: 12, border: "1px solid #ccc", borderRadius: 8, boxSizing: "border-box", font: "inherit" }} />
              <p><small>Each answer is saved when you continue. If you lose your connection, sign in again and you will return to this question. A saved answer cannot be changed.</small></p>
              <button style={primary} onClick={save} disabled={busy || !answer.trim()}>Save answer and continue</button>
            </>
          ) : (
            <>
              <h2>All questions answered</h2>
              <button style={primary} onClick={finish} disabled={busy}>Finish interview</button>
            </>
          )}
          <button style={plain} onClick={() => setState(null)} disabled={busy}>Pause and go back</button>
        </section>
      ) : (
        <>
          {items.map((item) => {
            const open = item.status === "scheduled" || item.status === "in_progress";
            const ready = open && item.candidate_response !== "declined" && item.consent_given && item.questions_total > 0;
            return (
              <section key={item.id} style={panel}>
                <h2>{item.job_title}</h2>
                <p>
                  {item.scheduled_at ? `${new Date(item.scheduled_at).toLocaleString()} (shown in your local time)` : "Time to be confirmed"} · {item.duration_minutes} minutes · Status: <strong>{item.status}</strong>
                </p>
                {item.meeting_url && <p>Meeting link: <a href={item.meeting_url} target="_blank" rel="noreferrer">{item.meeting_url}</a></p>}
                {item.status === "scheduled" && (
                  <p>
                    Your reply: <strong>{item.candidate_response}</strong>
                    <button style={plain} onClick={() => respond(item.id, "confirmed")} disabled={busy || item.candidate_response === "confirmed"}>Confirm</button>
                    <button style={plain} onClick={() => respond(item.id, "declined")} disabled={busy || item.candidate_response === "declined"}>Decline</button>
                  </p>
                )}
                {open && item.candidate_response !== "declined" && (
                  <>
                    {!item.consent_given ? (
                      <div>
                        <label>
                          <input type="checkbox" checked={!!agree[item.id]} onChange={(e) => setAgree({ ...agree, [item.id]: e.target.checked })} />{" "}
                          I agree that my written answers are stored and read by the recruiters for this job. No automatic hiring decision is made.
                        </label>
                        <br />
                        <button style={primary} onClick={() => consent(item.id, true)} disabled={busy || !agree[item.id]}>Give consent</button>
                      </div>
                    ) : (
                      <p>Consent given. <button style={plain} onClick={() => consent(item.id, false)} disabled={busy}>Withdraw consent</button></p>
                    )}
                    {item.questions_total === 0 && <p>The questions are not ready yet. Please check again later.</p>}
                    <button style={primary} onClick={() => start(item.id)} disabled={busy || !ready}>
                      {item.questions_answered > 0 ? `Continue interview (${item.questions_answered} of ${item.questions_total} answered)` : "Start interview"}
                    </button>
                  </>
                )}
                {item.status === "completed" && <p>You have finished this interview. Thank you.</p>}
              </section>
            );
          })}
          {session && !items.length && <p>You have no interviews yet.</p>}
        </>
      )}
    </main>
  );
}
