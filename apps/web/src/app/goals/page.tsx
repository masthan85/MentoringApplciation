"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Levels = { minus_two: string; minus_one: string; zero: string; plus_one: string; plus_two: string };
type Goal = {
  id: string;
  title: string;
  status: string;
  current_score: number;
  current_level_text: string;
  levels: Record<string, string>;
  milestones: { id: string; title: string; due_date: string | null; status: string }[];
};
type Commitment = { id: string; title: string; due_date: string | null; status: string; goal_id: string | null; source: string };

const LEVEL_KEYS: [keyof Levels, string][] = [
  ["minus_two", "−2  Much less than expected"],
  ["minus_one", "−1  Less than expected"],
  ["zero", "0  Expected outcome"],
  ["plus_one", "+1  More than expected"],
  ["plus_two", "+2  Much more than expected"],
];
const EMPTY: Levels = { minus_two: "", minus_one: "", zero: "", plus_one: "", plus_two: "" };

export default function GoalsPage() {
  return (
    <AppShell>
      <Goals />
    </AppShell>
  );
}

function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [title, setTitle] = useState("");
  const [baseline, setBaseline] = useState("");
  const [levels, setLevels] = useState<Levels>(EMPTY);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [commitTitle, setCommitTitle] = useState("");
  const [commitDue, setCommitDue] = useState("");
  const [busy, setBusy] = useState(false);

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);

  useEffect(() => {
    void (async () => {
      const [g, c] = await Promise.all([api.GET("/v1/goals"), api.GET("/v1/commitments")]);
      if (g.data) setGoals(g.data as unknown as Goal[]);
      if (c.data) setCommitments(c.data as unknown as Commitment[]);
    })();
  }, [version]);

  async function suggest() {
    setBusy(true);
    setError("");
    const { data, error: failure } = await api.POST("/v1/goals/suggest-levels", {
      body: { title, baseline: baseline || null, target: null },
    });
    setBusy(false);
    if (data) {
      setLevels(data as unknown as Levels);
      setNote("These are suggestions. Edit any of them so they describe your real situation.");
    } else {
      setNote(failure ? "I could not suggest levels just now. Please write them yourself." : "");
    }
  }

  async function createGoal(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const { error: failure } = await api.POST("/v1/goals", {
      body: { title, baseline: baseline || null, baseline_score: -1, levels },
    });
    if (failure) {
      setError("Every level needs a short description, and the goal needs a title.");
      return;
    }
    setTitle("");
    setBaseline("");
    setLevels(EMPTY);
    setNote("");
    load();
  }

  async function score(goal: Goal, value: number) {
    await api.POST("/v1/goals/{goal_id}/scores", { params: { path: { goal_id: goal.id } }, body: { score: value } });
    load();
  }

  async function addCommitment(event: React.FormEvent) {
    event.preventDefault();
    const { error: failure } = await api.POST("/v1/commitments", {
      body: { title: commitTitle, due_date: commitDue || null },
    });
    if (failure) {
      setError("A commitment needs a title of at least three characters.");
      return;
    }
    setCommitTitle("");
    setCommitDue("");
    load();
  }

  async function setStatus(c: Commitment, status: "done" | "dropped") {
    await api.PATCH("/v1/commitments/{commitment_id}", {
      params: { path: { commitment_id: c.id } },
      body: { status },
    });
    load();
  }

  const open = commitments.filter((c) => c.status === "open");

  return (
    <div className="space-y-8">
      <section aria-labelledby="g-h">
        <h1 id="g-h" className="mb-2 text-xl font-semibold">Goals</h1>
        {goals.length === 0 && <p style={{ color: "var(--muted)" }}>No goals yet.</p>}
        <ul className="space-y-3">
          {goals.map((g) => (
            <li key={g.id} className="rounded border p-3" style={{ borderColor: "var(--line)" }}>
              <div className="font-medium">{g.title}</div>
              <label className="text-sm">
                Where are you now?{" "}
                <select
                  aria-label={`Current level for ${g.title}`}
                  value={String(g.current_score)}
                  onChange={(e) => void score(g, Number(e.target.value))}
                  className="rounded border bg-transparent p-1"
                  style={{ borderColor: "var(--line)" }}
                >
                  {[-2, -1, 0, 1, 2].map((n) => (
                    <option key={n} value={n}>
                      {n > 0 ? "+" : ""}
                      {n}: {g.levels[String(n)]}
                    </option>
                  ))}
                </select>
              </label>
              {g.milestones.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-sm">
                  {g.milestones.map((m) => (
                    <li key={m.id}>
                      {m.title} {m.status === "done" ? "(done)" : ""}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </section>

      <form onSubmit={createGoal} className="space-y-3" aria-labelledby="new-goal">
        <h2 id="new-goal" className="font-medium">Set a goal</h2>
        <label className="block text-sm">
          What do you want to achieve?
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <label className="block text-sm">
          Where are you now, in your own words?
          <input value={baseline} onChange={(e) => setBaseline(e.target.value)} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <button type="button" onClick={() => void suggest()} disabled={busy || title.length < 3} className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }}>
          Suggest levels
        </button>
        {note && <p role="status" className="text-sm" style={{ color: "var(--muted)" }}>{note}</p>}
        {LEVEL_KEYS.map(([key, label]) => (
          <label key={key} className="block text-sm">
            {label}
            <input value={levels[key]} onChange={(e) => setLevels({ ...levels, [key]: e.target.value })} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
          </label>
        ))}
        <button className="rounded px-4 py-2 text-sm" style={{ background: "var(--accent)", color: "var(--background)" }}>
          Save goal
        </button>
      </form>

      <section aria-labelledby="c-h" className="space-y-3">
        <h2 id="c-h" className="font-medium">Commitments</h2>
        {open.length === 0 && <p style={{ color: "var(--muted)" }}>Nothing open.</p>}
        <ul className="space-y-2">
          {open.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded border p-3 text-sm" style={{ borderColor: "var(--line)" }}>
              <span>
                {c.title}
                {c.due_date ? ` (by ${c.due_date})` : ""}
              </span>
              <span className="flex gap-3">
                <button onClick={() => void setStatus(c, "done")} className="underline">Done</button>
                <button onClick={() => void setStatus(c, "dropped")} className="underline">Drop</button>
              </span>
            </li>
          ))}
        </ul>
        <form onSubmit={addCommitment} className="flex flex-wrap items-end gap-2 text-sm">
          <label>
            New commitment
            <input value={commitTitle} onChange={(e) => setCommitTitle(e.target.value)} className="mt-1 block rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
          </label>
          <label>
            By
            <input type="date" value={commitDue} onChange={(e) => setCommitDue(e.target.value)} className="mt-1 block rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
          </label>
          <button className="rounded border px-3 py-2" style={{ borderColor: "var(--line)" }}>Add</button>
        </form>
      </section>
      {error && <p role="alert" className="text-sm">{error}</p>}
    </div>
  );
}
