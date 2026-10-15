"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/browser-api";

type Lens = { id: string; name: string; pack: string };

export function PersonaPicker({
  current,
  onChanged,
}: {
  current: string[];
  onChanged: (names: string[]) => void;
}) {
  const [lenses, setLenses] = useState<Lens[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<{ mode: string; names: string[] } | null>(null);
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");

  useEffect(() => {
    void (async () => {
      const [list, now] = await Promise.all([api.GET("/v1/personas"), api.GET("/v1/personas/active")]);
      if (list.data) setLenses(list.data);
      if (now.data) setActive({ mode: now.data.mode, names: now.data.names });
    })();
  }, []);

  const names = current.length ? current : (active?.names ?? []);

  async function apply(mode: "auto" | "pinned") {
    const lens_ids = mode === "pinned" ? [first, second].filter(Boolean) : [];
    if (mode === "pinned" && lens_ids.length === 0) return;
    const { data } = await api.PUT("/v1/personas/active", { body: { mode, lens_ids } });
    if (data) {
      setActive({ mode: data.mode, names: data.names });
      onChanged(data.names);
      setOpen(false);
    }
  }

  return (
    <div className="text-sm" style={{ color: "var(--muted)" }}>
      <p>
        Mentoring as:{" "}
        <span style={{ color: "var(--foreground)" }}>{names.length ? names.join(" and ").toLowerCase() : "…"}</span>
        {active?.mode === "pinned" && " (chosen by you)"} ·{" "}
        <button className="underline" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          change
        </button>
      </p>
      {open && (
        <div className="mt-2 flex flex-col gap-2 rounded-md border p-3" style={{ borderColor: "var(--line)" }}>
          <label className="flex flex-col gap-1">
            Main perspective
            <select
              value={first}
              onChange={(e) => setFirst(e.target.value)}
              className="rounded border bg-transparent px-2 py-1"
              style={{ borderColor: "var(--line)", color: "var(--foreground)" }}
            >
              <option value="">Choose…</option>
              {lenses.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Blend with (optional)
            <select
              value={second}
              onChange={(e) => setSecond(e.target.value)}
              className="rounded border bg-transparent px-2 py-1"
              style={{ borderColor: "var(--line)", color: "var(--foreground)" }}
            >
              <option value="">None</option>
              {lenses
                .filter((l) => l.id !== first)
                .map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
            </select>
          </label>
          <div className="flex gap-3">
            <button className="underline" onClick={() => void apply("pinned")} disabled={!first}>
              Use this
            </button>
            <button className="underline" onClick={() => void apply("auto")}>
              Let the mentor choose
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
