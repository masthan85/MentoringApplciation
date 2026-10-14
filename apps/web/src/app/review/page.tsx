"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ProgressChart, type Series } from "@/components/ProgressChart";
import { api } from "@/lib/browser-api";

type Status = {
  due: boolean;
  goals: { id: string; title: string; current_score: number; levels: Record<string, string> }[];
  self_efficacy_items: string[];
  working_alliance_items: string[];
};
type Trends = {
  goals: { id: string; title: string; points: { at: string; score: number }[] }[];
  self_efficacy: { at: string; value: number }[];
  working_alliance: { at: string; value: number }[];
};

export default function ReviewPage() {
  return (
    <AppShell>
      <Review />
    </AppShell>
  );
}

function Review() {
  const [status, setStatus] = useState<Status | null>(null);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [efficacy, setEfficacy] = useState([3, 3, 3]);
  const [alliance, setAlliance] = useState([3, 3, 3]);
  const [reflection, setReflection] = useState("");
  const [done, setDone] = useState("");
  const [shown, setShown] = useState(false);

  const [version, setVersion] = useState(0);

  useEffect(() => {
    void (async () => {
      const [s, t] = await Promise.all([api.GET("/v1/reviews/quarterly/status"), api.GET("/v1/reviews/trends")]);
      if (s.data) {
        const st = s.data as unknown as Status;
        setStatus(st);
        setScores(Object.fromEntries(st.goals.map((g) => [g.id, g.current_score])));
      }
      if (t.data) setTrends(t.data as unknown as Trends);
    })();
  }, [version]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const { error } = await api.POST("/v1/reviews/quarterly", {
      body: { gas_scores: scores, self_efficacy: efficacy, working_alliance: alliance, reflection: reflection || null },
    });
    setDone(error ? "That did not save. Check each answer and try again." : "Review saved.");
    if (!error) {
      setShown(false);
      setVersion((v) => v + 1);
    }
  }

  if (!status || !trends) return <p role="status">Loading…</p>;
  const series: Series[] = trends.goals.map((g) => ({ id: g.id, title: g.title, points: g.points }));
  const last = (xs: { value: number }[]) => (xs.length ? xs[xs.length - 1]!.value.toFixed(1) : "none yet");

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Progress review</h1>
      <ProgressChart series={series} />
      <dl className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt style={{ color: "var(--muted)" }}>Confidence (latest, 1 to 5)</dt>
          <dd className="text-lg font-medium">{last(trends.self_efficacy)}</dd>
        </div>
        <div>
          <dt style={{ color: "var(--muted)" }}>How well mentoring is working (latest, 1 to 5)</dt>
          <dd className="text-lg font-medium">{last(trends.working_alliance)}</dd>
        </div>
      </dl>
      <p className="text-xs" style={{ color: "var(--muted)" }}>
        These short questions are our own, not a validated research instrument. Use them to see your own direction of travel.
      </p>
      {done && <p role="status">{done}</p>}
      {status.due || shown ? (
        <form onSubmit={submit} className="space-y-4">
          <h2 className="font-medium">Quarterly review</h2>
          {status.goals.map((g) => (
            <label key={g.id} className="block text-sm">
              {g.title}
              <select value={scores[g.id] ?? 0} onChange={(e) => setScores({ ...scores, [g.id]: Number(e.target.value) })} className="mt-1 block w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }}>
                {[-2, -1, 0, 1, 2].map((n) => (
                  <option key={n} value={n}>{n > 0 ? "+" : ""}{n}: {g.levels[String(n)]}</option>
                ))}
              </select>
            </label>
          ))}
          {[
            { items: status.self_efficacy_items, values: efficacy, set: setEfficacy },
            { items: status.working_alliance_items, values: alliance, set: setAlliance },
          ].map((group, gi) => (
            <fieldset key={gi} className="space-y-2">
              <legend className="text-sm font-medium">{gi === 0 ? "About you (1 = disagree, 5 = agree)" : "About mentoring (1 = disagree, 5 = agree)"}</legend>
              {group.items.map((item, i) => (
                <label key={i} className="block text-sm">
                  {item}
                  <input type="number" min={1} max={5} value={group.values[i]} onChange={(e) => group.set(group.values.map((v, j) => (j === i ? Number(e.target.value) : v)))} className="ml-2 w-16 rounded border bg-transparent p-1" style={{ borderColor: "var(--line)" }} />
                </label>
              ))}
            </fieldset>
          ))}
          <label className="block text-sm">
            Anything you want to note?
            <textarea value={reflection} onChange={(e) => setReflection(e.target.value)} rows={3} className="mt-1 w-full rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
          </label>
          <button className="rounded px-4 py-2 text-sm" style={{ background: "var(--accent)", color: "var(--background)" }}>Save review</button>
        </form>
      ) : (
        <button className="text-sm underline" onClick={() => setShown(true)}>Do a review now</button>
      )}
    </div>
  );
}
