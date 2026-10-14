"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/browser-api";
import { type ProfileCard, sendMessage } from "@/lib/stream";
import { PersonaPicker } from "./PersonaPicker";

type Line = { id: string; role: "user" | "assistant"; content: string; error?: boolean };
type Noted = { id: string; content: string; type: string; sensitivity: string; status: string };

export function Chat({
  conversationId,
  onProfile,
  showPersona = true,
  placeholder = "Write a message",
}: {
  conversationId: string;
  onProfile?: (card: ProfileCard) => void;
  showPersona?: boolean;
  placeholder?: string;
}) {
  const [lines, setLines] = useState<Line[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [persona, setPersona] = useState<string[]>([]);
  const [noted, setNoted] = useState<Noted[]>([]);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/conversations/{conversation_id}", {
        params: { path: { conversation_id: conversationId } },
      });
      if (data) {
        setLines(data.messages.map((m) => ({ id: m.id, role: m.role as Line["role"], content: m.content })));
      }
    })();
  }, [conversationId]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [lines]);

  const watchForMemories = useCallback(
    (since: string) => {
      // Memories are extracted in the background, so look a few times after the reply.
      for (const delay of [1500, 4000, 9000]) {
        setTimeout(async () => {
          const { data } = await api.GET("/v1/memories", {
            params: { query: { conversation_id: conversationId, since } },
          });
          if (!data?.length) return;
          setNoted((current) => {
            const known = new Set(current.map((n) => n.id));
            return [...current, ...data.filter((m) => !known.has(m.id))];
          });
        }, delay);
      }
    },
    [conversationId],
  );

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    const since = new Date(Date.now() - 1000).toISOString();
    const assistantId = `pending-${Date.now()}`;
    setLines((l) => [
      ...l,
      { id: `user-${Date.now()}`, role: "user", content: text },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    await sendMessage(conversationId, text, (event) => {
      if (event.type === "meta") setPersona(event.persona.names);
      if (event.type === "delta") {
        setLines((l) => l.map((x) => (x.id === assistantId ? { ...x, content: x.content + event.text } : x)));
      }
      if (event.type === "error") {
        setLines((l) => l.map((x) => (x.id === assistantId ? { ...x, content: event.message, error: true } : x)));
      }
      if (event.type === "done") {
        if (event.profile) onProfile?.(event.profile);
        watchForMemories(since);
      }
    }).catch(() => {
      setLines((l) =>
        l.map((x) =>
          x.id === assistantId && !x.content
            ? { ...x, content: "The connection was interrupted. Please try again.", error: true }
            : x,
        ),
      );
    });
    setBusy(false);
  }

  async function undo(id: string) {
    await api.DELETE("/v1/memories/{memory_id}", { params: { path: { memory_id: id } } });
    setNoted((n) => n.filter((m) => m.id !== id));
  }

  async function confirm(id: string) {
    await api.POST("/v1/memories/{memory_id}/confirm", { params: { path: { memory_id: id } } });
    setNoted((n) => n.map((m) => (m.id === id ? { ...m, status: "active" } : m)));
  }

  return (
    <div className="flex flex-col gap-4">
      {showPersona && (
        <PersonaPicker current={persona} onChanged={(names) => setPersona(names)} />
      )}
      <div
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        className="flex min-h-[40vh] flex-col gap-4"
      >
        {lines.length === 0 && (
          <p style={{ color: "var(--muted)" }}>Nothing here yet. Say hello, or ask the first thing on your mind.</p>
        )}
        {lines.map((line) => (
          <div
            key={line.id}
            className={line.role === "user" ? "self-end max-w-[85%]" : "self-start max-w-[92%]"}
            data-role={line.role}
          >
            <p className="mb-1 text-xs" style={{ color: "var(--muted)" }}>
              {line.role === "user" ? "You" : "Mentor"}
            </p>
            <p
              className="whitespace-pre-wrap rounded-lg px-3 py-2"
              style={{
                background: line.role === "user" ? "var(--line)" : "transparent",
                border: line.role === "user" ? "none" : "1px solid var(--line)",
                color: line.error ? "#b3261e" : "inherit",
              }}
            >
              {line.content || (busy ? "…" : "")}
            </p>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      {noted.length > 0 && (
        <ul aria-label="Things the mentor noted" className="flex flex-col gap-2 text-sm">
          {noted.map((memory) => (
            <li
              key={memory.id}
              className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-1.5"
              style={{ borderColor: "var(--line)" }}
            >
              <span>
                {memory.status === "pending" ? "Sensitive, not saved yet: " : "Noted: "}
                {memory.content}
              </span>
              {memory.status === "pending" && (
                <button className="underline" onClick={() => void confirm(memory.id)}>
                  Keep
                </button>
              )}
              <button className="underline" onClick={() => void undo(memory.id)}>
                {memory.status === "pending" ? "Discard" : "Undo"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <label htmlFor="message" className="sr-only">
          Message
        </label>
        <textarea
          id="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          rows={2}
          maxLength={8000}
          placeholder={placeholder}
          className="flex-1 resize-none rounded-md border bg-transparent px-3 py-2"
          style={{ borderColor: "var(--line)" }}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent)", color: "var(--background)" }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
