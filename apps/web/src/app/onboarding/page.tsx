"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Chat } from "@/components/Chat";
import { ProfileCard, cardKey } from "@/components/ProfileCard";
import { api } from "@/lib/browser-api";
import type { ProfileCard as Card } from "@/lib/stream";

export default function Onboarding() {
  return (
    <AppShell>
      <OnboardingInner />
    </AppShell>
  );
}

function OnboardingInner() {
  const router = useRouter();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [card, setCard] = useState<Card | null>(null);

  useEffect(() => {
    void (async () => {
      const [conversation, profile] = await Promise.all([
        api.POST("/v1/conversations", { body: { kind: "onboarding" } }),
        api.GET("/v1/profile"),
      ]);
      if (conversation.data) setConversationId(conversation.data.id);
      if (profile.data) setCard(profile.data as unknown as Card);
    })();
  }, []);

  if (!conversationId || !card) return <p style={{ color: "var(--muted)" }}>Getting ready…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Let&rsquo;s get to know you</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          A few questions, about ten minutes. Say hello to start.
        </p>
      </div>
      <Chat
        conversationId={conversationId}
        showPersona={false}
        placeholder="Tell me a bit about your work"
        onProfile={(next) => setCard(next)}
      />
      <ProfileCard
        key={cardKey(card)}
        card={card}
        confirmLabel="This looks right"
        onSaved={(next) => setCard(next)}
        onConfirmed={() => router.push("/chat")}
      />
    </div>
  );
}
