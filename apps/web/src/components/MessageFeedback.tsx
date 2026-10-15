"use client";

import { useState } from "react";
import { api } from "@/lib/browser-api";

type Kind = "thumbs_up" | "thumbs_down" | "not_like_me";

export function MessageFeedback({ messageId, draftId }: { messageId?: string; draftId?: string }) {
  const [sent, setSent] = useState<Kind | null>(null);

  async function send(kind: Kind) {
    const { response } = await api.POST("/v1/feedback", {
      body: { kind, message_id: messageId ?? null, draft_id: draftId ?? null },
    });
    if (response.ok) setSent(kind);
  }

  if (sent) {
    return (
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }} role="status">
        Thanks, noted.
      </p>
    );
  }
  const button = "underline";
  return (
    <p className="mt-1 flex gap-3 text-xs" style={{ color: "var(--muted)" }}>
      <button className={button} onClick={() => void send("thumbs_up")}>
        Helpful
      </button>
      <button className={button} onClick={() => void send("thumbs_down")}>
        Not helpful
      </button>
      <button className={button} onClick={() => void send("not_like_me")}>
        Doesn&rsquo;t sound like me
      </button>
    </p>
  );
}
