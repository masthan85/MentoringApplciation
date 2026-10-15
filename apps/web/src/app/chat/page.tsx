"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Chat } from "@/components/Chat";
import { api } from "@/lib/browser-api";

type Conversation = { id: string; title: string | null; kind: string };

export default function ChatPage() {
  return (
    <AppShell>
      <ChatInner />
    </AppShell>
  );
}

function ChatInner() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [current, setCurrent] = useState<string | null>(null);

  const start = useCallback(async () => {
    const { data } = await api.POST("/v1/conversations", { body: { kind: "mentoring" } });
    if (data) {
      setCurrent(data.id);
      setConversations((c) => [{ id: data.id, title: null, kind: "mentoring" }, ...c]);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const profile = await api.GET("/v1/profile");
      if (profile.data?.onboarding_status !== "complete") {
        router.replace("/onboarding");
        return;
      }
      const { data } = await api.GET("/v1/conversations");
      const mentoring = (data ?? []).filter((c) => c.kind === "mentoring");
      setConversations(mentoring);
      if (mentoring[0]) setCurrent(mentoring[0].id);
      else await start();
    })();
  }, [router, start]);

  if (!current) return <p style={{ color: "var(--muted)" }}>Getting ready…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="sr-only">Conversation</span>
          <select
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="max-w-[16rem] rounded border bg-transparent px-2 py-1"
            style={{ borderColor: "var(--line)" }}
          >
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title ?? "New conversation"}
              </option>
            ))}
          </select>
        </label>
        <button className="underline" onClick={() => void start()}>
          New conversation
        </button>
      </div>
      <Chat key={current} conversationId={current} />
    </div>
  );
}
