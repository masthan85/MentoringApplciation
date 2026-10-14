"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Run = {
  id: string;
  label: string;
  mode: string;
  status: string;
  summary: { ok?: boolean; deterministic_passed?: number; scenarios?: number; cost_usd?: number; failures?: { id: string; reasons?: string[] }[] };
  started_at: string;
};

export default function AdminEvalsPage() {
  return (
    <AppShell>
      <Evals />
    </AppShell>
  );
}

function Evals() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [label, setLabel] = useState("");
  const [mode, setMode] = useState<"smoke" | "full">("smoke");
  const [message, setMessage] = useState("");

  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/admin/evals");
      if (data) setRuns(data as unknown as Run[]);
    })();
  }, [version]);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    const { error } = await api.POST("/v1/admin/evals", { body: { mode, label: label || "manual run", packs: null } });
    setMessage(error ? "Could not start the run." : "Run started. Refresh in a minute.");
    load();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Evaluation runs</h1>
      <form onSubmit={start} className="flex flex-wrap items-end gap-2 text-sm">
        <label>
          Label
          <input value={label} onChange={(e) => setLabel(e.target.value)} className="mt-1 block rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <label>
          Mode
          <select value={mode} onChange={(e) => setMode(e.target.value as "smoke" | "full")} className="mt-1 block rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }}>
            <option value="smoke">Smoke (free, deterministic)</option>
            <option value="full">Full (real models, costs money)</option>
          </select>
        </label>
        <button className="rounded border px-3 py-2" style={{ borderColor: "var(--line)" }}>Start run</button>
      </form>
      {message && <p role="status" className="text-sm">{message}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left"><th>When</th><th>Label</th><th>Mode</th><th>Status</th><th>Passed</th></tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
              <td>{r.started_at.slice(0, 16).replace("T", " ")}</td>
              <td>{r.label}</td>
              <td>{r.mode}</td>
              <td>{r.status}</td>
              <td>
                {r.summary.scenarios ? `${r.summary.deterministic_passed}/${r.summary.scenarios}` : "–"}
                {r.summary.failures?.map((f) => (
                  <div key={f.id} style={{ color: "var(--muted)" }}>{f.id}</div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
