"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ProfileCard, cardKey } from "@/components/ProfileCard";
import { WritingStyle } from "@/components/WritingStyle";
import { api, download } from "@/lib/browser-api";
import type { ProfileCard as Card } from "@/lib/stream";

type Memory = { id: string; type: string; content: string; sensitivity: string; status: string };

const CONSENT_LABELS: Record<string, string> = {
  sensitive_memory: "Remember sensitive things I tell you (I will always ask before keeping each one)",
  fingerprint_learning: "Learn from my edits to drafts",
  mentor_sharing: "Allow sharing briefs with a human mentor I invite",
  analytics: "Share anonymous usage analytics",
};

export default function NotesPage() {
  return (
    <AppShell>
      <Notes />
    </AppShell>
  );
}

function Notes() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [card, setCard] = useState<Card | null>(null);
  const [consents, setConsents] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [text, setText] = useState("");

  useEffect(() => {
    void (async () => {
      const [m, p, c] = await Promise.all([api.GET("/v1/memories"), api.GET("/v1/profile"), api.GET("/v1/consents")]);
      if (m.data) setMemories(m.data);
      if (p.data) setCard(p.data as unknown as Card);
      if (c.data) setConsents(c.data);
    })();
  }, []);

  async function remove(id: string) {
    await api.DELETE("/v1/memories/{memory_id}", { params: { path: { memory_id: id } } });
    setMemories((all) => all.filter((m) => m.id !== id));
  }

  async function saveEdit(id: string) {
    const { data } = await api.PATCH("/v1/memories/{memory_id}", {
      params: { path: { memory_id: id } },
      body: { content: text },
    });
    if (data) setMemories((all) => all.map((m) => (m.id === id ? data : m)));
    setEditing(null);
  }

  async function confirm(id: string) {
    const { data } = await api.POST("/v1/memories/{memory_id}/confirm", { params: { path: { memory_id: id } } });
    if (data) setMemories((all) => all.map((m) => (m.id === id ? data : m)));
  }

  async function toggle(purpose: string, granted: boolean) {
    const before = consents;
    setConsents({ ...consents, [purpose]: granted }); // show the change at once
    const { data } = await api.PUT("/v1/consents/{purpose}", {
      params: { path: { purpose } },
      body: { granted },
    });
    setConsents(data ?? before); // the server's answer, or back to where we were
  }

  async function removeAll() {
    if (!window.confirm("Delete everything the mentor remembers about you? This cannot be undone.")) return;
    await api.DELETE("/v1/memories", { params: { query: { all: true } } });
    setMemories([]);
  }

  const groups = memories.reduce<Record<string, Memory[]>>((acc, m) => {
    (acc[m.type] ??= []).push(m);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-semibold">My mentor&rsquo;s notes</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Everything the mentor remembers about you. Edit it, delete it, or take a copy.
        </p>
      </div>

      <section aria-labelledby="mem-title">
        <h2 id="mem-title" className="mb-2 font-medium">
          What I remember
        </h2>
        {memories.length === 0 && <p style={{ color: "var(--muted)" }}>Nothing yet.</p>}
        {Object.entries(groups).map(([type, items]) => (
          <div key={type} className="mb-4">
            <h3 className="text-xs uppercase tracking-wide" style={{ color: "var(--muted)" }}>
              {type.replace(/_/g, " ")}
            </h3>
            <ul className="mt-1 flex flex-col gap-2">
              {items.map((memory) => (
                <li key={memory.id} className="rounded-md border px-3 py-2" style={{ borderColor: "var(--line)" }}>
                  {editing === memory.id ? (
                    <div className="flex flex-col gap-2">
                      <label className="sr-only" htmlFor={`edit-${memory.id}`}>
                        Edit memory
                      </label>
                      <textarea
                        id={`edit-${memory.id}`}
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        rows={2}
                        className="rounded border bg-transparent px-2 py-1"
                        style={{ borderColor: "var(--line)" }}
                      />
                      <div className="flex gap-3 text-sm">
                        <button className="underline" onClick={() => void saveEdit(memory.id)}>
                          Save
                        </button>
                        <button className="underline" onClick={() => setEditing(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span>
                        {memory.content}
                        {memory.sensitivity === "sensitive" && (
                          <span className="ml-2 text-xs" style={{ color: "var(--muted)" }}>
                            (sensitive{memory.status === "pending" ? ", waiting for you to keep it" : ""})
                          </span>
                        )}
                      </span>
                      <span className="flex gap-3 text-sm">
                        {memory.status === "pending" && (
                          <button className="underline" onClick={() => void confirm(memory.id)}>
                            Keep
                          </button>
                        )}
                        <button
                          className="underline"
                          onClick={() => {
                            setEditing(memory.id);
                            setText(memory.content);
                          }}
                        >
                          Edit
                        </button>
                        <button className="underline" onClick={() => void remove(memory.id)}>
                          Delete
                        </button>
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
        {memories.length > 0 && (
          <button className="text-sm underline" onClick={() => void removeAll()}>
            Delete everything
          </button>
        )}
      </section>

      {card && <ProfileCard key={cardKey(card)} card={card} onSaved={(next) => setCard(next)} />}

      <WritingStyle />

      <section aria-labelledby="consent-title">
        <h2 id="consent-title" className="mb-2 font-medium">
          Your choices
        </h2>
        <ul className="flex flex-col gap-2 text-sm">
          {Object.entries(CONSENT_LABELS).map(([purpose, label]) => (
            <li key={purpose}>
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={consents[purpose] ?? false}
                  onChange={(e) => void toggle(purpose, e.target.checked)}
                  className="mt-1"
                />
                {label}
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="export-title">
        <h2 id="export-title" className="mb-2 font-medium">
          Take a copy
        </h2>
        <div className="flex gap-4 text-sm">
          <button className="underline" onClick={() => void download("/v1/memories/export?format=json", "mentor-notes.json")}>
            Download as JSON
          </button>
          <button className="underline" onClick={() => void download("/v1/memories/export?format=markdown", "mentor-notes.md")}>
            Download as Markdown
          </button>
        </div>
      </section>
    </div>
  );
}
