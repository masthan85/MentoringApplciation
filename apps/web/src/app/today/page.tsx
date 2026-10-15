"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/browser-api";

type Today = {
  next_commitment: { id: string; title: string; due_date: string | null; overdue: boolean } | null;
  nudge: { kind: string; text: string; link: string };
  check_in_due: boolean;
  quarterly_review_due: boolean;
  goals: { id: string; title: string; current_score: number; baseline_score: number; level_text: string }[];
  open_commitments: number;
};

export default function TodayPage() {
  return (
    <AppShell>
      <TodayView />
    </AppShell>
  );
}

function TodayView() {
  const [today, setToday] = useState<Today | null>(null);
  const [reminders, setReminders] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void (async () => {
      const [t, p] = await Promise.all([api.GET("/v1/today"), api.GET("/v1/profile")]);
      if (t.data) setToday(t.data as unknown as Today);
      if (p.data) setReminders(Boolean(p.data.email_reminders));
    })();
  }, []);

  async function toggleReminders(on: boolean) {
    setReminders(on);
    const { error } = await api.PUT("/v1/profile", { body: { confirm_onboarding: false, email_reminders: on } });
    setMessage(error ? "That did not save. Please try again." : on ? "Email reminders are on." : "Email reminders are off.");
  }

  if (!today) return <p role="status">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Today</h1>
      {today.nudge.text && (
        <section className="rounded border p-4" style={{ borderColor: "var(--line)" }} aria-label="What to do next">
          <p>{today.nudge.text}</p>
          <Link href={today.nudge.link} className="mt-2 inline-block text-sm underline underline-offset-4">
            Go there
          </Link>
        </section>
      )}
      <section aria-labelledby="goals-h">
        <h2 id="goals-h" className="mb-2 font-medium">
          Your goals
        </h2>
        {today.goals.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>
            No goals yet. <Link href="/goals" className="underline">Set your first one</Link>, or ask the mentor to help you choose.
          </p>
        ) : (
          <ul className="space-y-2">
            {today.goals.map((g) => (
              <li key={g.id} className="rounded border p-3" style={{ borderColor: "var(--line)" }}>
                <div className="font-medium">{g.title}</div>
                <div className="text-sm" style={{ color: "var(--muted)" }}>
                  Now: {g.level_text || "not yet scored"} ({g.current_score > 0 ? "+" : ""}
                  {g.current_score}; started at {g.baseline_score > 0 ? "+" : ""}
                  {g.baseline_score})
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <nav aria-label="Progress" className="flex gap-4 text-sm">
        <Link href="/goals" className="underline underline-offset-4">Goals and commitments</Link>
        <Link href="/check-in" className="underline underline-offset-4">Weekly check-in</Link>
        <Link href="/review" className="underline underline-offset-4">Progress review</Link>
      </nav>
      <section className="text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={reminders} onChange={(e) => void toggleReminders(e.target.checked)} />
          Email me a reminder for my weekly check-in (no private detail is included)
        </label>
        {message && <p role="status">{message}</p>}
      </section>
    </div>
  );
}
