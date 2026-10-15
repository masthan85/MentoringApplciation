"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { MessageFeedback } from "@/components/MessageFeedback";
import { api } from "@/lib/browser-api";

const CHANNELS: Record<string, string> = {
  email: "Email",
  slack: "Slack or Teams message",
  exec_summary: "Executive summary",
  adr: "Architecture decision record",
  linkedin: "LinkedIn post",
  interview_spoken: "Spoken interview answer",
};
const RECIPIENTS: Record<string, string> = {
  cto: "CTO",
  executive: "Executive",
  manager: "My manager",
  peer: "A peer",
  team: "My team",
  stakeholder: "A stakeholder",
  recruiter: "Recruiter",
  hiring_manager: "Hiring manager",
  other: "Someone else",
};
const FLAG_LABELS: Record<string, string> = {
  discourse_markers: "stacked transition words",
  formulaic_opener: "a generic opener",
  formulaic_closer: "a generic closer",
  question_restatement: "repeating the brief",
  redundant_conclusion: "a closing paragraph that repeats the body",
  empty_adjectives: "vague praise words",
  repeated_phrases: "repeated phrases",
  repeated_openings: "sentences that start the same way",
  sentence_variation: "sentences of very similar length",
  list_ratio: "a lot of bullet points",
  heading_ratio: "headings",
  length: "length",
};

type Draft = {
  id?: string | null;
  refused?: string | null;
  message?: string | null;
  text?: string | null;
  adjusted: boolean;
  adjustment_note?: string | null;
  lint?: { passed: boolean; failed: string[] } | null;
  lint_after_adjustment?: { failed: string[] } | null;
  similarity?: number | null;
  warnings: string[];
};

export default function StudioPage() {
  return (
    <AppShell>
      <Studio />
    </AppShell>
  );
}

function Studio() {
  const [channel, setChannel] = useState("email");
  const [recipient, setRecipient] = useState("manager");
  const [purpose, setPurpose] = useState("");
  const [points, setPoints] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [edited, setEdited] = useState("");
  const [saved, setSaved] = useState("");

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved("");
    setDraft(null);
    const { data, error: failure } = await api.POST("/v1/studio/drafts", {
      body: { channel: channel as never, recipient: recipient as never, purpose, key_points: points },
    });
    setBusy(false);
    if (data) {
      setDraft(data as unknown as Draft);
      setEdited(data.text ?? "");
    } else {
      const detail = (failure as { detail?: string } | undefined)?.detail;
      setError(detail ?? "Something went wrong. Please check the form and try again.");
    }
  }

  async function saveEdits() {
    if (!draft?.id) return;
    const { data } = await api.POST("/v1/studio/drafts/{draft_id}/edit", {
      params: { path: { draft_id: draft.id } },
      body: { final_text: edited },
    });
    setSaved(
      data?.learned
        ? "Saved. The mentor learned from your edits."
        : `Saved.${data?.reason ? ` ${data.reason}` : ""}`,
    );
  }

  const field = "w-full rounded-md border bg-transparent px-3 py-2";
  const border = { borderColor: "var(--line)" };
  const flagged = draft?.lint && !draft.lint.passed ? draft.lint.failed.map((f) => FLAG_LABELS[f] ?? f) : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Studio</h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Draft something to send in your own name, in your own voice. Give the facts you want in it; the draft will
          not add any.
        </p>
      </div>
      <form onSubmit={create} className="flex flex-col gap-3 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            What are you writing?
            <select className={field} style={border} value={channel} onChange={(e) => setChannel(e.target.value)}>
              {Object.entries(CHANNELS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            Who is it for?
            <select className={field} style={border} value={recipient} onChange={(e) => setRecipient(e.target.value)}>
              {Object.entries(RECIPIENTS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1">
          What is it for?
          <input className={field} style={border} value={purpose} onChange={(e) => setPurpose(e.target.value)} required minLength={5} maxLength={1000} />
        </label>
        <label className="flex flex-col gap-1">
          The facts and points to include
          <textarea className={field} style={border} rows={5} value={points} onChange={(e) => setPoints(e.target.value)} required minLength={5} maxLength={4000} />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="self-start rounded-md px-4 py-2 font-medium disabled:opacity-50"
          style={{ background: "var(--accent)", color: "var(--background)" }}
        >
          {busy ? "Writing…" : "Write a draft"}
        </button>
        <p role="alert" style={{ color: "#b3261e" }}>
          {error}
        </p>
      </form>

      {draft?.refused && (
        <p role="alert" className="whitespace-pre-wrap rounded-md border p-3" style={border}>
          {draft.message}
        </p>
      )}

      {draft && !draft.refused && (
        <section aria-labelledby="draft-title" className="flex flex-col gap-3">
          <h2 id="draft-title" className="font-medium">
            Your draft
          </h2>
          <label className="sr-only" htmlFor="draft-text">
            Draft text
          </label>
          <textarea id="draft-text" className={field} style={border} rows={12} value={edited} onChange={(e) => setEdited(e.target.value)} />
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <button className="underline" onClick={() => void saveEdits()}>
              Save my edits
            </button>
            <button className="underline" onClick={() => void navigator.clipboard?.writeText(edited)}>
              Copy
            </button>
            <span role="status" style={{ color: "var(--muted)" }}>
              {saved}
            </span>
          </div>
          <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--muted)" }}>
            {draft.adjustment_note && <li>{draft.adjustment_note}</li>}
            {flagged.length > 0 && !draft.adjusted && <li>Things you may want to smooth: {flagged.join(", ")}.</li>}
            {draft.lint?.passed && <li>Reads naturally: no stacked transitions, filler or repeated phrasing found.</li>}
            {draft.similarity != null ? (
              <li>Closeness to your own writing style: {Math.round(draft.similarity * 100)}%.</li>
            ) : (
              <li>Add writing samples in My notes and this will show how close the draft is to your style.</li>
            )}
          </ul>
          {draft.warnings.map((w) => (
            <p key={w} role="alert" className="rounded-md border p-2 text-sm" style={border}>
              {w}
            </p>
          ))}
          {draft.id && <MessageFeedback draftId={draft.id} />}
        </section>
      )}
    </div>
  );
}
