"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/browser-api";

const MODES: Record<string, string> = {
  natural_professional: "Natural professional (default)",
  professional: "Professional",
  executive: "Executive",
  conversational: "Conversational",
  technical: "Technical",
  academic: "Academic",
  concise: "Concise",
  detailed: "Detailed",
  my_style: "My style (needs writing samples)",
};
const CHANNELS: Record<string, string> = {
  chat: "Chat",
  slack: "Slack or Teams",
  email: "Email",
  exec_summary: "Executive summary",
  adr: "Design note or ADR",
  linkedin: "LinkedIn post",
  interview_spoken: "Spoken answer",
};

type Sample = { id: string; channel: string; origin: string; word_count: number; preview: string };
type Style = { sample_count: number; voice_cards: Record<string, string>; voice_card_override: string | null };

export function WritingStyle() {
  const [mode, setMode] = useState("natural_professional");
  const [variant, setVariant] = useState("en-GB");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [style, setStyle] = useState<Style | null>(null);
  const [channel, setChannel] = useState("email");
  const [text, setText] = useState("");
  const [own, setOwn] = useState(false);
  const [override, setOverride] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const [list, profile] = await Promise.all([api.GET("/v1/writing-samples"), api.GET("/v1/style-profile")]);
    if (list.data) setSamples(list.data as Sample[]);
    if (profile.data) {
      setStyle(profile.data as Style);
      setOverride(profile.data.voice_card_override ?? "");
    }
  }

  useEffect(() => {
    void (async () => {
      const [prefs, list, profile] = await Promise.all([
        api.GET("/v1/profile"),
        api.GET("/v1/writing-samples"),
        api.GET("/v1/style-profile"),
      ]);
      if (prefs.data) {
        setMode(prefs.data.writing_mode);
        setVariant(prefs.data.english_variant);
      }
      if (list.data) setSamples(list.data as Sample[]);
      if (profile.data) {
        setStyle(profile.data as Style);
        setOverride(profile.data.voice_card_override ?? "");
      }
    })();
  }, []);

  async function savePrefs(next: { writing_mode?: string; english_variant?: string }) {
    const { response } = await api.PUT("/v1/profile", { body: { ...next, confirm_onboarding: false } });
    setMessage(response.ok ? "Saved." : "That could not be saved.");
  }

  async function addSample(event: React.FormEvent) {
    event.preventDefault();
    setMessage("");
    const { error } = await api.POST("/v1/writing-samples", { body: { channel, text, confirm_own: own } });
    if (error) {
      setMessage((error as { detail?: string }).detail ?? "That could not be added.");
      return;
    }
    setText("");
    setOwn(false);
    setMessage("Added.");
    await refresh();
  }

  async function removeSample(id: string) {
    await api.DELETE("/v1/writing-samples/{sample_id}", { params: { path: { sample_id: id } } });
    await refresh();
  }

  async function saveOverride() {
    await api.PUT("/v1/style-profile/voice-card", { body: { voice_card: override.trim() || null } });
    setMessage("Saved.");
    await refresh();
  }

  async function removeAll() {
    if (!window.confirm("Delete your writing samples and your style profile? This cannot be undone.")) return;
    await api.DELETE("/v1/style-profile");
    setMessage("Deleted.");
    await refresh();
  }

  const border = { borderColor: "var(--line)" };
  const input = "w-full rounded-md border bg-transparent px-2 py-1.5";
  const description = style?.voice_cards?.overall;

  return (
    <section aria-labelledby="writing-title" className="flex flex-col gap-5 text-sm">
      <h2 id="writing-title" className="font-medium">
        How the mentor writes
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          Writing mode
          <select
            className={input}
            style={border}
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              void savePrefs({ writing_mode: e.target.value });
            }}
          >
            {Object.entries(MODES).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Spelling
          <select
            className={input}
            style={border}
            value={variant}
            onChange={(e) => {
              setVariant(e.target.value);
              void savePrefs({ english_variant: e.target.value });
            }}
          >
            <option value="en-GB">British English</option>
            <option value="en-US">American English</option>
          </select>
        </label>
      </div>
      <p role="status" style={{ color: "var(--muted)" }}>
        {message}
      </p>

      <div>
        <h3 className="mb-1 font-medium">Your writing style</h3>
        <p style={{ color: "var(--muted)" }}>
          Add a few things you wrote yourself, and the mentor can match your style. It describes your style and never
          copies mistakes. About 120 words in total per kind of writing are needed before a description appears.
        </p>
        {description ? (
          <p className="mt-2 rounded-md border p-3" style={border}>
            {description}
          </p>
        ) : (
          <p className="mt-2" style={{ color: "var(--muted)" }}>
            Not enough writing yet to describe your style.
          </p>
        )}
        <label className="mt-3 flex flex-col gap-1">
          Or describe it in your own words (this replaces the description above)
          <textarea className={input} style={border} rows={2} maxLength={1500} value={override} onChange={(e) => setOverride(e.target.value)} />
        </label>
        <button className="mt-1 underline" onClick={() => void saveOverride()}>
          Save description
        </button>
      </div>

      <ul aria-label="Your writing samples" className="flex flex-col gap-2">
        {samples.map((s) => (
          <li key={s.id} className="flex items-start justify-between gap-3 rounded-md border p-2" style={border}>
            <span>
              <span style={{ color: "var(--muted)" }}>
                {CHANNELS[s.channel] ?? s.channel} · {s.word_count} words · {s.origin === "draft_edit" ? "from a draft you edited" : "added by you"}
              </span>
              <br />
              {s.preview}
            </span>
            <button className="underline" onClick={() => void removeSample(s.id)}>
              Delete
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={addSample} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1">
          Kind of writing
          <select className={input} style={border} value={channel} onChange={(e) => setChannel(e.target.value)}>
            {Object.entries(CHANNELS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          Something you wrote
          <textarea className={input} style={border} rows={5} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" checked={own} onChange={(e) => setOwn(e.target.checked)} className="mt-1" />I wrote this myself.
          Never add other people&rsquo;s writing.
        </label>
        <button type="submit" className="self-start underline" disabled={!text.trim()}>
          Add sample
        </button>
      </form>

      {(style?.sample_count ?? 0) > 0 && (
        <button className="self-start underline" onClick={() => void removeAll()}>
          Delete my writing samples and style profile
        </button>
      )}
    </section>
  );
}
