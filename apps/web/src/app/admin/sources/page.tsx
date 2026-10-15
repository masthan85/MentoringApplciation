"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Source = {
  id: string;
  slug: string;
  title: string;
  status: string;
  authority_tier: string;
  domain: string;
  chunk_count: number;
  review_flags: string[];
  reviewer: string | null;
  last_reviewed: string | null;
};

const TEMPLATE = `---
slug: my-source-slug
title: "Title of the source"
publisher: "Who published it"
url: "https://example.org/page"
authority_tier: expert_authored   # official, standard, peer_reviewed, expert_authored or community
volatility: moderate              # stable, moderate or volatile
domain: data_engineering          # or data_architecture, ai_ml, genai, security, leadership, career, communication, general
jurisdiction: global              # global, GB, EU or US
licence: "How we are allowed to use it"
reviewer: "Name of the expert who checked it"
published_date: 2026-01-01
last_reviewed: 2026-10-01
---
# Heading
Text of the source, in Markdown.
`;

export default function AdminSourcesPage() {
  return (
    <AppShell>
      <AdminSources />
    </AppShell>
  );
}

function AdminSources() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [document, setDocument] = useState(TEMPLATE);
  const [message, setMessage] = useState("");
  const [acknowledged, setAcknowledged] = useState<Record<string, boolean>>({});

  async function load() {
    const { data, response } = await api.GET("/v1/admin/sources");
    if (response.status === 403) setForbidden(true);
    else if (data) setSources(data as unknown as Source[]);
  }

  useEffect(() => {
    void (async () => {
      const { data, response } = await api.GET("/v1/admin/sources");
      if (response.status === 403) setForbidden(true);
      else if (data) setSources(data as unknown as Source[]);
    })();
  }, []);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setMessage("");
    const { data, error } = await api.POST("/v1/admin/sources", { body: { document, kind: "markdown" } });
    if (data) {
      setMessage(
        `Added "${data.slug}" as ${data.status}: ${data.chunks} sections, ${data.embedded} embedded.` +
          (data.findings.length ? ` Flags: ${data.findings.join(", ")}.` : ""),
      );
      await load();
    } else {
      setMessage((error as { detail?: string } | undefined)?.detail ?? "That could not be added.");
    }
  }

  async function setStatus(source: Source, status: "active" | "retired" | "draft") {
    const { error } = await api.PATCH("/v1/admin/sources/{source_id}", {
      params: { path: { source_id: source.id } },
      body: { status, acknowledge_flags: acknowledged[source.id] ?? false },
    });
    setMessage(error ? ((error as { detail?: string }).detail ?? "Could not change the status.") : "");
    await load();
  }

  async function remove(source: Source) {
    if (!window.confirm(`Delete "${source.title}" for good?`)) return;
    await api.DELETE("/v1/admin/sources/{source_id}", { params: { path: { source_id: source.id } } });
    await load();
  }

  if (forbidden) return <p>Admin access is required.</p>;
  if (!sources) return <p style={{ color: "var(--muted)" }}>Loading…</p>;

  const border = { borderColor: "var(--line)" };
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-semibold">Encyclopedia sources</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Only active sources are used in answers. New and changed sources start as drafts. A source flagged by the scan
          needs you to read it and tick the box before it can be activated.
        </p>
      </div>
      <p role="status" className="text-sm">
        {message}
      </p>
      <ul className="flex flex-col gap-3">
        {sources.map((source) => (
          <li key={source.id} className="rounded-md border p-3 text-sm" style={border}>
            <p className="font-medium">{source.title}</p>
            <p style={{ color: "var(--muted)" }}>
              {source.slug} · {source.status} · {source.authority_tier} · {source.domain} · {source.chunk_count} sections
              {source.reviewer ? ` · reviewed by ${source.reviewer}` : " · no reviewer yet"}
            </p>
            {source.review_flags.length > 0 && (
              <p role="alert" className="mt-1">
                Flags: {source.review_flags.join(", ")}
                <label className="ml-3">
                  <input
                    type="checkbox"
                    checked={acknowledged[source.id] ?? false}
                    onChange={(e) => setAcknowledged({ ...acknowledged, [source.id]: e.target.checked })}
                  />{" "}
                  I have read it and it is safe
                </label>
              </p>
            )}
            <p className="mt-2 flex gap-4">
              {source.status !== "active" && (
                <button className="underline" onClick={() => void setStatus(source, "active")}>
                  Activate
                </button>
              )}
              {source.status === "active" && (
                <button className="underline" onClick={() => void setStatus(source, "retired")}>
                  Retire
                </button>
              )}
              <button className="underline" onClick={() => void remove(source)}>
                Delete
              </button>
            </p>
          </li>
        ))}
        {sources.length === 0 && <li style={{ color: "var(--muted)" }}>No sources yet.</li>}
      </ul>

      <form onSubmit={add} className="flex flex-col gap-2 text-sm">
        <label htmlFor="doc" className="font-medium">
          Add a source (Markdown with a front matter block)
        </label>
        <textarea
          id="doc"
          rows={16}
          value={document}
          onChange={(e) => setDocument(e.target.value)}
          className="rounded-md border bg-transparent px-3 py-2 font-mono text-xs"
          style={border}
        />
        <button
          type="submit"
          className="self-start rounded-md px-4 py-2 font-medium"
          style={{ background: "var(--accent)", color: "var(--background)" }}
        >
          Add as draft
        </button>
      </form>
    </div>
  );
}
