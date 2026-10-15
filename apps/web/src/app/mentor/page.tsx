"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Mentee = { link_id: string; accepted_at: string | null };
type Section = { title: string; text: string };

export default function MentorPage() {
  return (
    <AppShell>
      <MentorWorkspace />
    </AppShell>
  );
}

function MentorWorkspace() {
  const urlToken = useSyncExternalStore(
    () => () => {},
    () => new URLSearchParams(window.location.search).get("token") ?? "",
    () => "",
  );
  const [token, setToken] = useState<string | null>(null);
  const [mentees, setMentees] = useState<Mentee[]>([]);
  const [version, setVersion] = useState(0);
  const [brief, setBrief] = useState<Record<string, Section[] | null>>({});
  const [summary, setSummary] = useState<Record<string, string>>({});
  const [action, setAction] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const code = token ?? urlToken;

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/mentor/mentees");
      if (data) setMentees(data as unknown as Mentee[]);
    })();
  }, [version]);

  async function accept(event: React.FormEvent) {
    event.preventDefault();
    const { response } = await api.POST("/v1/mentor/accept", { body: { token: code } });
    if (response.ok) {
      setMessage("You are now linked. The mentee decides what you can see.");
      setToken("");
      setVersion((v) => v + 1);
    } else setMessage("That invitation is not valid for this account. Sign in with the email address it was sent to.");
  }

  async function view(id: string) {
    const { data } = await api.GET("/v1/mentor/mentees/{link_id}/brief", { params: { path: { link_id: id } } });
    setBrief({ ...brief, [id]: data ? (data as unknown as { content: { sections: Section[] } }).content.sections : null });
    if (!data) setMessage("They have not shared an approved brief yet.");
  }

  async function addNote(id: string) {
    const actions = (action[id] ?? "").split("\n").map((t) => t.trim()).filter((t) => t.length >= 3).map((title) => ({ title }));
    const { response } = await api.POST("/v1/mentor/mentees/{link_id}/notes", { params: { path: { link_id: id } }, body: { summary: summary[id] ?? "", actions } });
    setMessage(response.ok ? "Saved. The mentee will see your notes, and any actions as suggestions for them to accept." : "I could not save that.");
    if (response.ok) setSummary({ ...summary, [id]: "" });
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Mentor workspace</h1>
      <form onSubmit={accept} className="space-y-2">
        <label className="block text-sm">
          Invitation code
          <input value={code} onChange={(e) => setToken(e.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <button className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }}>Accept invitation</button>
      </form>
      {message && <p role="status" className="text-sm">{message}</p>}
      <section aria-labelledby="m-h" className="space-y-4">
        <h2 id="m-h" className="font-medium">Your mentees</h2>
        {mentees.length === 0 && <p style={{ color: "var(--muted)" }}>No one has linked with you yet.</p>}
        {mentees.map((m, i) => (
          <article key={m.link_id} className="space-y-3 rounded border p-4" style={{ borderColor: "var(--line)" }}>
            <h3 className="font-medium">Mentee {i + 1}</h3>
            <button className="text-sm underline" onClick={() => void view(m.link_id)}>View their approved brief</button>
            {brief[m.link_id] && (
              <div className="space-y-2 text-sm">
                {brief[m.link_id]!.map((s, j) => (
                  <div key={j}><strong>{s.title}</strong><div className="whitespace-pre-wrap">{s.text}</div></div>
                ))}
              </div>
            )}
            <label className="block text-sm">
              Session notes
              <textarea value={summary[m.link_id] ?? ""} onChange={(e) => setSummary({ ...summary, [m.link_id]: e.target.value })} rows={3} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
            </label>
            <label className="block text-sm">
              Suggested actions (one per line; the mentee chooses whether to accept)
              <textarea value={action[m.link_id] ?? ""} onChange={(e) => setAction({ ...action, [m.link_id]: e.target.value })} rows={2} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
            </label>
            <button className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }} onClick={() => void addNote(m.link_id)}>Save notes</button>
          </article>
        ))}
      </section>
    </div>
  );
}
