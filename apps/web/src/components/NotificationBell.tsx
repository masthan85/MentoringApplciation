"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/browser-api";

type Item = { id: string; title: string; body: string | null; link: string | null; read_at: string | null };

export function NotificationBell() {
  const [items, setItems] = useState<Item[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const [version, setVersion] = useState(0);

  useEffect(() => {
    void (async () => {
      const { data } = await api.GET("/v1/notifications");
      if (data) {
        setItems(data.items as unknown as Item[]);
        setUnread(data.unread);
      }
    })();
  }, [version]);

  async function markAllRead() {
    await api.POST("/v1/notifications/read");
    setVersion((v) => v + 1);
  }

  return (
    <div className="relative">
      <button aria-expanded={open} onClick={() => setOpen(!open)} className="text-sm">
        Notifications{unread > 0 ? ` (${unread})` : ""}
      </button>
      {open && (
        <div role="region" aria-label="Notifications" className="absolute right-0 z-10 mt-2 w-72 rounded border p-3 text-sm shadow" style={{ background: "var(--background)", borderColor: "var(--line)" }}>
          {items.length === 0 && <p style={{ color: "var(--muted)" }}>Nothing new.</p>}
          <ul className="space-y-2">
            {items.slice(0, 8).map((n) => (
              <li key={n.id} style={{ opacity: n.read_at ? 0.6 : 1 }}>
                {n.link ? <Link href={n.link} onClick={() => setOpen(false)} className="underline">{n.title}</Link> : n.title}
                {n.body && <div style={{ color: "var(--muted)" }}>{n.body}</div>}
              </li>
            ))}
          </ul>
          {unread > 0 && <button onClick={() => void markAllRead()} className="mt-2 underline">Mark all read</button>}
        </div>
      )}
    </div>
  );
}
