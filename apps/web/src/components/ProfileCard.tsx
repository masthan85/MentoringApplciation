"use client";

import { useState } from "react";
import { api } from "@/lib/browser-api";
import { useRegions } from "@/lib/regions";
import type { ProfileCard as Card } from "@/lib/stream";

export const ROLES: Record<string, string> = {
  data_engineer: "Data engineer",
  data_architect: "Data architect",
  analytics_engineer: "Analytics engineer",
  ml_ai_engineer: "ML or AI engineer",
  software_engineer: "Software engineer",
  tech_lead: "Tech lead",
  engineering_manager: "Engineering manager",
  other: "Something else",
};
export const LEVELS: Record<string, string> = {
  junior: "Junior",
  mid: "Mid-level",
  senior: "Senior",
  lead: "Lead or principal",
  executive: "Executive",
};
const FIELD_LABELS: Record<string, string> = {
  country: "country",
  role_family: "role",
  seniority: "seniority",
  stack: "tools",
  goals_summary: "goals",
  current_challenge: "current challenge",
};

type Draft = {
  country: string;
  role_family: string;
  seniority: string;
  job_title: string;
  years_experience: string;
  stack: string;
  goals_summary: string;
  current_challenge: string;
};

function browserTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

function toDraft(card: Card): Draft {
  return {
    country: card.country ?? "",
    role_family: card.role_family ?? "",
    seniority: card.seniority ?? "",
    job_title: card.job_title ?? "",
    years_experience: card.years_experience?.toString() ?? "",
    stack: card.stack.join(", "),
    goals_summary: card.goals_summary ?? "",
    current_challenge: card.current_challenge ?? "",
  };
}

/** Remount key: pass it as `key` so the form resets when the server-side profile changes. */
export function cardKey(card: Card): string {
  return JSON.stringify(card);
}

export function ProfileCard({
  card,
  confirmLabel,
  onSaved,
  onConfirmed,
}: {
  card: Card;
  confirmLabel?: string;
  onSaved?: (card: Card) => void;
  onConfirmed?: () => void;
}) {
  const regions = useRegions();
  const [draft, setDraft] = useState<Draft>(toDraft(card));
  const [message, setMessage] = useState("");

  const set = (key: keyof Draft) => (value: string) => setDraft((d) => ({ ...d, [key]: value }));

  function body(confirm: boolean) {
    return {
      country: draft.country || undefined,
      // The browser knows the real time zone; the server only knows the country's usual one.
      timezone: card.timezone ? undefined : browserTimeZone(),
      role_family: (draft.role_family || undefined) as never,
      seniority: (draft.seniority || undefined) as never,
      job_title: draft.job_title || undefined,
      years_experience: draft.years_experience ? Number(draft.years_experience) : undefined,
      stack: draft.stack
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      goals_summary: draft.goals_summary,
      current_challenge: draft.current_challenge,
      confirm_onboarding: confirm,
    };
  }

  async function save(confirm: boolean) {
    setMessage("");
    const { data, error } = await api.PUT("/v1/profile", { body: body(confirm) });
    if (data) {
      onSaved?.(data as unknown as Card);
      if (confirm) onConfirmed?.();
      else setMessage("Saved.");
    } else {
      const missing = (error as { missing_fields?: string[] } | undefined)?.missing_fields;
      setMessage(
        missing?.length
          ? `Still needed: ${missing.map((m) => FIELD_LABELS[m] ?? m).join(", ")}.`
          : "That could not be saved. Please check the details.",
      );
    }
  }

  const input = "w-full rounded-md border bg-transparent px-2 py-1.5";
  const border = { borderColor: "var(--line)" };

  return (
    <section aria-labelledby="card-title" className="rounded-lg border p-4" style={border}>
      <h2 id="card-title" className="font-medium">
        Here is what I understood
      </h2>
      <p className="mb-3 text-sm" style={{ color: "var(--muted)" }}>
        Correct anything that is wrong. You can change this whenever you like.
      </p>
      <div className="flex flex-col gap-3 text-sm">
        <label className="flex flex-col gap-1">
          Country you work in
          <select className={input} style={border} value={draft.country} onChange={(e) => set("country")(e.target.value)}>
            <option value="">Choose a country</option>
            {regions.map((r) => (
              <option key={r.code} value={r.code}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Role
          <select className={input} style={border} value={draft.role_family} onChange={(e) => set("role_family")(e.target.value)}>
            <option value="">Not sure yet</option>
            {Object.entries(ROLES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Seniority
          <select className={input} style={border} value={draft.seniority} onChange={(e) => set("seniority")(e.target.value)}>
            <option value="">Not sure yet</option>
            {Object.entries(LEVELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Job title
          <input className={input} style={border} value={draft.job_title} onChange={(e) => set("job_title")(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          Years of experience
          <input
            className={input}
            style={border}
            inputMode="numeric"
            value={draft.years_experience}
            onChange={(e) => set("years_experience")(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        <label className="flex flex-col gap-1">
          Tools and technologies (comma separated)
          <input className={input} style={border} value={draft.stack} onChange={(e) => set("stack")(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          What you want from mentoring
          <textarea className={input} style={border} rows={3} value={draft.goals_summary} onChange={(e) => set("goals_summary")(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          The main challenge right now
          <textarea className={input} style={border} rows={3} value={draft.current_challenge} onChange={(e) => set("current_challenge")(e.target.value)} />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className="underline" onClick={() => void save(false)}>
          Save changes
        </button>
        {confirmLabel && (
          <button
            className="rounded-md px-4 py-2 text-sm font-medium"
            style={{ background: "var(--accent)", color: "var(--background)" }}
            onClick={() => void save(true)}
          >
            {confirmLabel}
          </button>
        )}
        <span role="status" className="text-sm" style={{ color: "var(--muted)" }}>
          {message}
        </span>
      </div>
    </section>
  );
}
