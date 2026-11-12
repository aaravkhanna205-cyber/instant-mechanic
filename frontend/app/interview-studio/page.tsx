"use client";
import { useEffect, useState } from "react";
import { api, type Interview, type Organization, type Session } from "../../lib/api/phase3";

type Detail = {
  id: string; job_title: string; status: string; scheduled_at: string | null; timezone: string;
  duration_minutes: number; meeting_url: string | null; candidate_response: string; candidate_note: string | null;
  questions_total: number; questions_answered: number;
};
type Question = { id: string; position: number; text: string };
type Report = {
  items: { position: number; question: string; answer: string | null; word_count: number }[];
  requirement_mentions: { requirement: string; mentioned_in_answers: boolean; matched_words: string[] }[];
  minutes_taken: number | null;
  decision: { decision: string; note: string; decided_at: string | null } | null;
  notice: string;
};

const panel: React.CSSProperties = { background: "white", border: "1px solid #e8e1d7", borderRadius: 14, padding: 22, marginBottom: 18 };
const field: React.CSSProperties = { padding: 10, width: "100%", border: "1px solid #ccc", borderRadius: 8, marginTop: 6, boxSizing: "border-box", font: "inherit" };
const primary: React.CSSProperties = { padding: "10px 16px", background: "#ffbd22", border: 0, borderRadius: 9, cursor: "pointer", fontWeight: 600, marginTop: 12, marginRight: 8 };
const plain: React.CSSProperties = { ...primary, background: "white", border: "1px solid #d8cfc0" };

function toLocalInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function fail(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function InterviewStudio() {
  const [session, setSession] = useState<Session | null>(null);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [org, setOrg] = useState("");
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [when, setWhen] = useState("");
  const [duration, setDuration] = useState(30);
  const [link, setLink] = useState("");
  const [approved, setApproved] = useState<Question[]>([]);
  const [drafts, setDrafts] = useState<string[]>([]);
  const [draftSource, setDraftSource] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [decision, setDecision] = useState("advance");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Session>("/api/auth/me")
      .then((s) => { setSession(s); return api<Organization[]>("/api/recruitment/organizations"); })
      .then(setOrgs)
      .catch((e) => setMessage(fail(e)));
  }, []);

  const base = (id: string) => `/api/interview-studio/organizations/${encodeURIComponent(org)}/interviews/${encodeURIComponent(id)}`;

  async function chooseOrg(value: string) {
    setOrg(value); setDetail(null); setInterviews([]); setApproved([]); setDrafts([]); setReport(null); setMessage("");
    if (!value) return;
    try { setInterviews(await api<Interview[]>(`/api/recruitment/organizations/${encodeURIComponent(value)}/interviews`)); }
    catch (e) { setMessage(fail(e)); }
  }

  async function open(id: string) {
    setDrafts([]); setDraftSource(""); setReport(null); setMessage("");
    if (!id) { setDetail(null); return; }
    try {
      const d = await api<Detail>(base(id));
      setDetail(d); setWhen(toLocalInput(d.scheduled_at)); setDuration(d.duration_minutes); setLink(d.meeting_url || "");
      setApproved(await api<Question[]>(`${base(id)}/questions`));
      if (d.status === "in_progress" || d.status === "completed") setReport(await api<Report>(`${base(id)}/report`));
    } catch (e) { setMessage(fail(e)); }
  }

  async function run(action: () => Promise<void>, done: string) {
    if (!session || !detail) return;
    setBusy(true); setMessage("Working...");
    try { await action(); setMessage(done); } catch (e) { setMessage(fail(e)); } finally { setBusy(false); }
  }

  const reschedule = () => run(async () => {
    if (!when) throw new Error("Choose a date and time first.");
    const body = {
      scheduled_at: new Date(when).toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata",
      duration_minutes: duration, meeting_url: link || null,
    };
    setDetail(await api<Detail>(`${base(detail!.id)}/schedule`, { method: "PATCH", body: JSON.stringify(body) }, session!.csrf_token));
  }, "New time saved. The candidate has been asked to confirm again.");

  const cancel = () => run(async () => {
    if (!window.confirm("Cancel this interview? The candidate will be notified.")) throw new Error("Not cancelled.");
    setDetail(await api<Detail>(`${base(detail!.id)}/cancel`, { method: "POST" }, session!.csrf_token));
  }, "Interview cancelled.");

  const makeDrafts = () => run(async () => {
    const result = await api<{ source: string; questions: string[] }>(`${base(detail!.id)}/questions/draft`, { method: "POST", body: JSON.stringify({ count: 6 }) }, session!.csrf_token);
    setDrafts(result.questions); setDraftSource(result.source);
  }, "Drafts ready. Edit them, then approve. Nothing is saved until you approve.");

  const approve = () => run(async () => {
    const questions = drafts.map((q) => q.trim()).filter(Boolean);
    if (!questions.length) throw new Error("Add at least one question.");
    setApproved(await api<Question[]>(`${base(detail!.id)}/questions`, { method: "PUT", body: JSON.stringify({ questions }) }, session!.csrf_token));
    setDrafts([]); setDraftSource("");
    setDetail(await api<Detail>(base(detail!.id)));
  }, "Questions approved and saved. The candidate can now take the interview.");

  const loadReport = () => run(async () => { setReport(await api<Report>(`${base(detail!.id)}/report`)); }, "Report loaded.");

  const saveDecision = () => run(async () => {
    await api(`${base(detail!.id)}/decision`, { method: "POST", body: JSON.stringify({ decision, note }) }, session!.csrf_token);
    setReport(await api<Report>(`${base(detail!.id)}/report`)); setNote("");
  }, "Decision recorded. No application stage was changed automatically.");

  const editable = detail?.status === "scheduled" && detail.questions_answered === 0;

  return (
    <main style={{ background: "#fdf9f2", minHeight: "100vh", padding: "48px 5%", color: "#171717" }}>
      <h1>Interview Studio</h1>
      <p>Schedule, approve questions, and review answers. Every question and every decision is approved by a person.</p>
      {!session && <p>Please <a href="/auth-live">sign in</a> as a recruiter first.</p>}
      <p role="status" style={{ minHeight: 24, color: "#8a4b00" }}>{message}</p>

      <section style={panel}>
        <label>Organization
          <select style={field} value={org} onChange={(e) => chooseOrg(e.target.value)}>
            <option value="">Choose...</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
        <label style={{ display: "block", marginTop: 14 }}>Interview
          <select style={field} value={detail?.id || ""} onChange={(e) => open(e.target.value)} disabled={!org}>
            <option value="">Choose...</option>
            {interviews.map((i) => (
              <option key={i.id} value={i.id}>
                {i.candidate_name || "Candidate"} · {i.job_title || "Job"} · {i.status}{i.scheduled_at ? ` · ${new Date(i.scheduled_at).toLocaleString()}` : ""}
              </option>
            ))}
          </select>
        </label>
        {org && !interviews.length && <p>No interviews yet. Schedule one from the Interviews page first.</p>}
      </section>

      {detail && (
        <>
          <section style={panel}>
            <h2>1. Schedule</h2>
            <p>
              Status: <strong>{detail.status}</strong> · Candidate reply: <strong>{detail.candidate_response}</strong>
              {detail.candidate_note ? ` (“${detail.candidate_note}”)` : ""} · Time zone on record: {detail.timezone}
            </p>
            <label>Date and time (your local time)
              <input style={field} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} disabled={detail.status !== "scheduled"} />
            </label>
            <label style={{ display: "block", marginTop: 10 }}>Length in minutes
              <input style={field} type="number" min={10} max={240} value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={detail.status !== "scheduled"} />
            </label>
            <label style={{ display: "block", marginTop: 10 }}>Meeting link (optional)
              <input style={field} type="url" placeholder="https://..." value={link} onChange={(e) => setLink(e.target.value)} disabled={detail.status !== "scheduled"} />
            </label>
            <button style={primary} onClick={reschedule} disabled={busy || detail.status !== "scheduled"}>Save new time</button>
            <button style={plain} onClick={cancel} disabled={busy || !["scheduled", "in_progress"].includes(detail.status)}>Cancel interview</button>
          </section>

          <section style={panel}>
            <h2>2. Questions</h2>
            <p>Approved questions: <strong>{approved.length}</strong>. The candidate sees only approved questions, one at a time.</p>
            <ol>{approved.map((q) => <li key={q.id} style={{ marginBottom: 6 }}>{q.text}</li>)}</ol>
            {editable ? (
              <>
                <button style={plain} onClick={makeDrafts} disabled={busy}>Suggest draft questions</button>
                <button style={plain} onClick={() => setDrafts(approved.length ? approved.map((q) => q.text) : [""])} disabled={busy}>Edit by hand</button>
                {draftSource && <p>Drafts written by: <strong>{draftSource === "local_ai" ? "the AI model on this PC" : "built-in rules"}</strong>. Read each one before approving.</p>}
                {drafts.map((text, index) => (
                  <div key={index} style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <textarea style={{ ...field, marginTop: 0 }} rows={2} maxLength={400} value={text}
                      onChange={(e) => setDrafts(drafts.map((d, i) => (i === index ? e.target.value : d)))} />
                    <button style={{ ...plain, marginTop: 0 }} onClick={() => setDrafts(drafts.filter((_, i) => i !== index))}>Remove</button>
                  </div>
                ))}
                {drafts.length > 0 && (
                  <>
                    <button style={plain} onClick={() => setDrafts([...drafts, ""])} disabled={drafts.length >= 12}>Add a question</button>
                    <button style={primary} onClick={approve} disabled={busy}>Approve and save these questions</button>
                  </>
                )}
              </>
            ) : <p>Questions are locked because the interview has started or is closed.</p>}
          </section>

          <section style={panel}>
            <h2>3. Answers and decision</h2>
            <p>Answered: {detail.questions_answered} of {detail.questions_total}</p>
            <button style={plain} onClick={loadReport} disabled={busy}>Load answers</button>
            {report && (
              <>
                <p><small>{report.notice}</small></p>
                {report.minutes_taken !== null && <p>Time taken: {report.minutes_taken} minutes</p>}
                {report.items.map((item) => (
                  <article key={item.position} style={{ borderTop: "1px solid #eee", padding: "12px 0" }}>
                    <strong>{item.position}. {item.question}</strong>
                    <p style={{ whiteSpace: "pre-wrap" }}>{item.answer ?? "Not answered yet."}</p>
                  </article>
                ))}
                {report.requirement_mentions.length > 0 && (
                  <>
                    <h3>Job requirements mentioned in the answers</h3>
                    <ul>{report.requirement_mentions.map((m) => (
                      <li key={m.requirement}>{m.requirement}: {m.mentioned_in_answers ? `mentioned (${m.matched_words.join(", ")})` : "not mentioned"}</li>
                    ))}</ul>
                  </>
                )}
                {report.decision && <p>Recorded decision: <strong>{report.decision.decision}</strong> — {report.decision.note}</p>}
                {detail.status === "completed" || report.items.every((i) => i.answer) ? (
                  <>
                    <label style={{ display: "block", marginTop: 12 }}>Your decision
                      <select style={field} value={decision} onChange={(e) => setDecision(e.target.value)}>
                        <option value="advance">Advance to the next step</option>
                        <option value="hold">Hold for now</option>
                        <option value="reject">Do not advance</option>
                      </select>
                    </label>
                    <label style={{ display: "block", marginTop: 10 }}>Reason (required)
                      <textarea style={field} rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What in the answers supports this decision?" />
                    </label>
                    <button style={primary} onClick={saveDecision} disabled={busy || note.trim().length < 4}>Record decision</button>
                  </>
                ) : <p>A decision can be recorded after the candidate finishes.</p>}
              </>
            )}
          </section>
        </>
      )}
      <a href="/interview-studio/session">Candidate interview page</a>
    </main>
  );
}
