"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Commitment = { id: string; title: string; due_date: string | null };
type CheckIn = { id: string; status: string; reply: string | null; safety_message: string | null; open_commitments: Commitment[] };
type Outcome = "done" | "partial" | "missed" | "dropped";

export default function CheckInPage() {
  return (
    <AppShell>
      <CheckInFlow />
    </AppShell>
  );
}

function CheckInFlow() {
  const [checkIn, setCheckIn] = useState<CheckIn | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [blockers, setBlockers] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/check-ins/current");
      if (data) setCheckIn(data as unknown as CheckIn);
    })();
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!checkIn) return;
    setBusy(true);
    const updates = Object.entries(outcomes).map(([commitment_id, outcome]) => ({ commitment_id, outcome }));
    const { data } = await api.POST("/v1/check-ins/{check_in_id}/complete", {
      params: { path: { check_in_id: checkIn.id } },
      body: { updates, blockers: blockers || null, next_commitment: next ? { title: next } : null },
    });
    setBusy(false);
    if (data) setCheckIn(data as unknown as CheckIn);
  }

  async function skip() {
    if (!checkIn) return;
    const { data } = await api.POST("/v1/check-ins/{check_in_id}/skip", { params: { path: { check_in_id: checkIn.id } } });
    if (data) setCheckIn(data as unknown as CheckIn);
  }

  if (!checkIn) return <p role="status">Loading…</p>;

  if (checkIn.status === "completed" || checkIn.status === "skipped") {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-semibold">{checkIn.status === "skipped" ? "Skipped this week" : "Check-in done"}</h1>
        {checkIn.safety_message && <p role="alert">{checkIn.safety_message}</p>}
        {checkIn.reply && <p>{checkIn.reply}</p>}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <h1 className="text-xl font-semibold">Weekly check-in</h1>
      {checkIn.open_commitments.length === 0 && <p style={{ color: "var(--muted)" }}>You have no open commitments.</p>}
      {checkIn.open_commitments.map((c) => (
        <fieldset key={c.id} className="rounded border p-3" style={{ borderColor: "var(--line)" }}>
          <legend className="px-1 text-sm">{c.title}</legend>
          {(["done", "partial", "missed", "dropped"] as Outcome[]).map((o) => (
            <label key={o} className="mr-4 text-sm">
              <input type="radio" name={c.id} checked={outcomes[c.id] === o} onChange={() => setOutcomes({ ...outcomes, [c.id]: o })} /> {o}
            </label>
          ))}
        </fieldset>
      ))}
      <label className="block text-sm">
        Anything getting in the way?
        <textarea value={blockers} onChange={(e) => setBlockers(e.target.value)} rows={3} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
      </label>
      <label className="block text-sm">
        One thing you will do this coming week
        <input value={next} onChange={(e) => setNext(e.target.value)} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
      </label>
      <div className="flex gap-3">
        <button disabled={busy} className="rounded px-4 py-2 text-sm" style={{ background: "var(--accent)", color: "var(--background)" }}>
          Finish check-in
        </button>
        <button type="button" onClick={() => void skip()} className="text-sm underline">Skip this week</button>
      </div>
    </form>
  );
}
