"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Chat } from "@/components/Chat";
import { api } from "@/lib/browser-api";

type Scenario = { id: string; title: string; summary: string; opening_hint: string };
type Debrief = { summary: string; strengths: string[]; improvements: string[]; stronger_phrases: string[]; next_step: string };
type Practice = { id: string; conversation_id: string; title: string; status: string; debrief: Debrief | null };

export default function PracticePage() {
  return (
    <AppShell>
      <PracticeInner />
    </AppShell>
  );
}

function PracticeInner() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [current, setCurrent] = useState<Practice | null>(null);
  const [context, setContext] = useState("");
  const [picked, setPicked] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/practice/scenarios");
      if (data) setScenarios(data);
    })();
  }, []);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const { data, response } = await api.POST("/v1/practice", { body: { scenario_id: picked, context: context || null } });
    if (data) setCurrent(data as unknown as Practice);
    else setError(response.status === 402 ? "Practice is part of a paid plan. See Settings." : "I could not set that up. Describe a real situation you want to rehearse.");
  }

  async function finish() {
    if (!current) return;
    setBusy(true);
    const { data } = await api.POST("/v1/practice/{practice_id}/finish", { params: { path: { practice_id: current.id } } });
    setBusy(false);
    if (data) setCurrent(data as unknown as Practice);
  }

  if (current) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{current.title}</h1>
          {current.status === "active" ? (
            <button onClick={() => void finish()} disabled={busy} className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }}>
              End and get feedback
            </button>
          ) : (
            <button onClick={() => setCurrent(null)} className="text-sm underline">Practise again</button>
          )}
        </div>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          This is a rehearsal with an AI playing a part. Nothing here is saved as a memory about you.
        </p>
        {current.debrief ? (
          <section aria-label="Feedback" className="space-y-3 rounded border p-4" style={{ borderColor: "var(--line)" }}>
            <p>{current.debrief.summary}</p>
            {[
              ["What worked", current.debrief.strengths],
              ["What to change", current.debrief.improvements],
              ["Phrases to try", current.debrief.stronger_phrases],
            ].map(([title, items]) =>
              (items as string[]).length > 0 ? (
                <div key={title as string}>
                  <h2 className="font-medium">{title as string}</h2>
                  <ul className="list-disc pl-5">{(items as string[]).map((t, i) => <li key={i}>{t}</li>)}</ul>
                </div>
              ) : null,
            )}
            {current.debrief.next_step && <p><strong>Next step:</strong> {current.debrief.next_step}</p>}
          </section>
        ) : (
          <Chat key={current.conversation_id} conversationId={current.conversation_id} showPersona={false} placeholder="Say your line" />
        )}
      </div>
    );
  }

  return (
    <form onSubmit={start} className="space-y-4">
      <h1 className="text-xl font-semibold">Practice</h1>
      <p style={{ color: "var(--muted)" }}>Rehearse a difficult conversation before the real one. You cannot use this during a live interview or assessment.</p>
      <fieldset className="space-y-2">
        <legend className="sr-only">Scenario</legend>
        {scenarios.map((s) => (
          <label key={s.id} className="block rounded border p-3" style={{ borderColor: picked === s.id ? "var(--accent)" : "var(--line)" }}>
            <input type="radio" name="scenario" value={s.id} checked={picked === s.id} onChange={() => setPicked(s.id)} className="mr-2" />
            <span className="font-medium">{s.title}</span>
            <span className="block text-sm" style={{ color: "var(--muted)" }}>{s.summary}</span>
          </label>
        ))}
      </fieldset>
      <label className="block text-sm">
        Describe your situation (optional)
        <textarea value={context} onChange={(e) => setContext(e.target.value)} maxLength={600} rows={3} placeholder={scenarios.find((s) => s.id === picked)?.opening_hint} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
      </label>
      {error && <p role="alert" className="text-sm">{error}</p>}
      <button disabled={!picked} className="rounded px-4 py-2 text-sm disabled:opacity-50" style={{ background: "var(--accent)", color: "var(--background)" }}>
        Start rehearsal
      </button>
    </form>
  );
}
