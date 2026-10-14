"use client";

import { useState } from "react";
import { api } from "@/lib/browser-api";

export type Source = {
  id: string;
  source_id: string;
  title: string;
  url: string | null;
  publisher: string | null;
  tier: string;
  published_date: string | null;
  last_reviewed: string | null;
};

const TIERS: Record<string, string> = {
  official: "Official",
  standard: "Standard",
  peer_reviewed: "Peer-reviewed",
  expert_authored: "Expert-authored",
  community: "Draft, not yet expert-reviewed",
};

export function Sources({ sources, asOf }: { sources: Source[]; asOf: string | null }) {
  if (sources.length === 0) return null;
  return (
    <div className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
      <p className="font-medium">Sources{asOf ? ` (most recent as of ${asOf})` : ""}</p>
      <ol className="mt-1 flex flex-col gap-1">
        {sources.map((s) => (
          <SourceRow key={s.id} source={s} />
        ))}
      </ol>
    </div>
  );
}

function SourceRow({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);

  async function toggle() {
    setOpen((o) => !o);
    if (text === null) {
      const { data } = await api.GET("/v1/sources/{source_id}", { params: { path: { source_id: source.source_id } } });
      setText(data ? data.chunks.map((c) => c.text).join("\n\n") : "This source is no longer available.");
    }
  }

  return (
    <li id={`source-${source.id}`}>
      <span style={{ color: "var(--foreground)" }}>[{source.id}]</span> {source.title}
      {source.publisher ? `, ${source.publisher}` : ""} · {TIERS[source.tier] ?? source.tier}
      {source.last_reviewed ? ` · reviewed ${source.last_reviewed}` : source.published_date ? ` · ${source.published_date}` : ""}
      {source.url && (
        <>
          {" "}
          <a className="underline" href={source.url} target="_blank" rel="noreferrer">
            open
          </a>
        </>
      )}{" "}
      <button className="underline" aria-expanded={open} onClick={() => void toggle()}>
        {open ? "hide text" : "see what it says"}
      </button>
      {open && (
        <p className="mt-1 whitespace-pre-wrap rounded border p-2" style={{ borderColor: "var(--line)", color: "var(--foreground)" }}>
          {text ?? "Loading…"}
        </p>
      )}
    </li>
  );
}

/** Turn [S1] markers into small links to the source list. */
export function withCitations(text: string): React.ReactNode[] {
  return text.split(/(\[S\d+\])/g).map((part, i) => {
    const match = /^\[(S\d+)\]$/.exec(part);
    if (!match) return part;
    return (
      <sup key={i}>
        <a href={`#source-${match[1]}`} className="underline" aria-label={`Source ${match[1]}`}>
          {match[1]}
        </a>
      </sup>
    );
  });
}
