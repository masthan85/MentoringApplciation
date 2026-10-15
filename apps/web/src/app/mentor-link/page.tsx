"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Link = { id: string; mentor_email: string; status: string };
type Section = { title: string; text: string };
type Brief = { id: string; status: string; content: { sections: Section[] } };
type Note = { id: string; summary: string; created_at: string };
type Commitment = { id: string; title: string; status: string; source: string };

export default function MentorLinkPage() {
  return (
    <AppShell>
      <MentorLink />
    </AppShell>
  );
}

function MentorLink() {
  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);
  const [links, setLinks] = useState<Link[]>([]);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [proposals, setProposals] = useState<Commitment[]>([]);
  const [email, setEmail] = useState("");
  const [goals, setGoals] = useState(true);
  const [commitments, setCommitments] = useState(true);
  const [invite, setInvite] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void (async () => {
      const [l, n, c] = await Promise.all([api.GET("/v1/mentor-link"), api.GET("/v1/session-notes"), api.GET("/v1/commitments")]);
      if (l.data) setLinks(l.data as unknown as Link[]);
      if (n.data) setNotes(n.data as unknown as Note[]);
      if (c.data) setProposals((c.data as unknown as Commitment[]).filter((x) => x.status === "proposed"));
    })();
  }, [version]);

  async function sendInvite(event: React.FormEvent) {
    event.preventDefault();
    setMessage("");
    const { data, response } = await api.POST("/v1/mentor-link", { body: { mentor_email: email, scopes: { goals, commitments } } });
    if (data) {
      setInvite((data as unknown as { invite_url: string }).invite_url);
      setEmail("");
      reload();
    } else if (response.status === 403) setMessage("First turn on “Allow sharing briefs with a human mentor” in My notes.");
    else if (response.status === 402) setMessage("A human mentor link is part of the Mentor + Human plan.");
    else setMessage("I could not create that invitation. Check the email address.");
  }

  async function makeBrief(id: string) {
    const { data } = await api.POST("/v1/mentor-link/{link_id}/briefs", { params: { path: { link_id: id } } });
    if (data) setBrief(data as unknown as Brief);
  }

  async function saveBrief(approve: boolean) {
    if (!brief) return;
    const saved = await api.PUT("/v1/mentor-briefs/{brief_id}", { params: { path: { brief_id: brief.id } }, body: brief.content });
    if (!saved.data) return;
    if (approve) {
      const { data } = await api.POST("/v1/mentor-briefs/{brief_id}/approve", { params: { path: { brief_id: brief.id } } });
      if (data) {
        setBrief(data as unknown as Brief);
        setMessage("Approved. Your mentor can now see exactly this and nothing else.");
      }
    } else setBrief(saved.data as unknown as Brief);
  }

  async function end(id: string) {
    if (!window.confirm("Stop sharing with this mentor? Any approved brief is deleted.")) return;
    await api.DELETE("/v1/mentor-link/{link_id}", { params: { path: { link_id: id } } });
    setBrief(null);
    reload();
  }

  async function answer(id: string, accept: boolean) {
    await api.POST(accept ? "/v1/commitments/{commitment_id}/accept" : "/v1/commitments/{commitment_id}/decline", { params: { path: { commitment_id: id } } });
    reload();
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Your human mentor</h1>

      {proposals.length > 0 && (
        <section aria-labelledby="prop-h" className="space-y-2">
          <h2 id="prop-h" className="font-medium">Suggested by your mentor</h2>
          <ul className="space-y-2">
            {proposals.map((p) => (
              <li key={p.id} className="flex items-center justify-between rounded border p-3 text-sm" style={{ borderColor: "var(--line)" }}>
                {p.title}
                <span className="flex gap-3">
                  <button className="underline" onClick={() => void answer(p.id, true)}>Accept</button>
                  <button className="underline" onClick={() => void answer(p.id, false)}>Decline</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="links-h" className="space-y-2">
        <h2 id="links-h" className="font-medium">Links</h2>
        {links.length === 0 && <p style={{ color: "var(--muted)" }}>No mentor linked yet.</p>}
        <ul className="space-y-2">
          {links.map((l) => (
            <li key={l.id} className="rounded border p-3 text-sm" style={{ borderColor: "var(--line)" }}>
              {l.mentor_email} · {l.status === "invited" ? "waiting for them to accept" : "active"}
              <span className="ml-3 inline-flex gap-3">
                {l.status === "active" && <button className="underline" onClick={() => void makeBrief(l.id)}>Prepare a brief</button>}
                <button className="underline" onClick={() => void end(l.id)}>Stop sharing</button>
              </span>
            </li>
          ))}
        </ul>
      </section>

      {brief && (
        <section aria-labelledby="brief-h" className="space-y-3">
          <h2 id="brief-h" className="font-medium">Brief for your mentor ({brief.status})</h2>
          <p className="text-sm" style={{ color: "var(--muted)" }}>Edit anything. Nothing is shared until you approve, and it never includes your memories or conversations.</p>
          {brief.content.sections.map((s, i) => (
            <label key={i} className="block text-sm">
              {s.title}
              <textarea
                value={s.text}
                rows={4}
                onChange={(e) => setBrief({ ...brief, content: { sections: brief.content.sections.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)) } })}
                className="mt-1 w-full rounded border bg-transparent p-2"
                style={{ borderColor: "var(--line)" }}
              />
            </label>
          ))}
          <div className="flex gap-3 text-sm">
            <button className="rounded border px-3 py-1" style={{ borderColor: "var(--line)" }} onClick={() => void saveBrief(false)}>Save draft</button>
            <button className="rounded px-3 py-1" style={{ background: "var(--accent)", color: "var(--background)" }} onClick={() => void saveBrief(true)}>Approve and share</button>
          </div>
        </section>
      )}

      <form onSubmit={sendInvite} className="space-y-3" aria-labelledby="inv-h">
        <h2 id="inv-h" className="font-medium">Invite a mentor</h2>
        <label className="block text-sm">
          Their email address
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <fieldset className="text-sm">
          <legend>What can go in the brief?</legend>
          <label className="mr-4"><input type="checkbox" checked={goals} onChange={(e) => setGoals(e.target.checked)} /> My goals</label>
          <label><input type="checkbox" checked={commitments} onChange={(e) => setCommitments(e.target.checked)} /> My commitments</label>
        </fieldset>
        <button className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }}>Create invitation</button>
        {invite && <p className="break-all text-sm" role="status">Send them this link (shown once): {invite}</p>}
      </form>
      {message && <p role="status" className="text-sm">{message}</p>}

      <section aria-labelledby="notes-h" className="space-y-2">
        <h2 id="notes-h" className="font-medium">Session notes</h2>
        {notes.length === 0 && <p style={{ color: "var(--muted)" }}>None yet.</p>}
        <ul className="space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="rounded border p-3 text-sm" style={{ borderColor: "var(--line)" }}>
              <div style={{ color: "var(--muted)" }}>{n.created_at.slice(0, 10)}</div>
              {n.summary}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
