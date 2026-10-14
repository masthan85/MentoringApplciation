"use client";

import { publicApiUrl } from "./api/client";
import { authHeaders } from "./browser-api";

export type TurnEvent =
  | { type: "meta"; persona: { names: string[]; lens_ids: string[]; source: string }; risk_class: string }
  | { type: "delta"; text: string }
  | { type: "done"; assistant_message_id: string; fixed_reply?: string; profile?: ProfileCard }
  | { type: "error"; message: string };

export type ProfileCard = {
  missing_fields: string[];
  role_family: string | null;
  seniority: string | null;
  job_title: string | null;
  years_experience: number | null;
  stack: string[];
  goals_summary: string | null;
  current_challenge: string | null;
  onboarding_status: string;
};

/** POST a message and read the Server-Sent Events reply as it arrives. */
export async function sendMessage(
  conversationId: string,
  content: string,
  onEvent: (event: TurnEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${publicApiUrl}/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!response.ok || !response.body) {
    onEvent({ type: "error", message: "Something went wrong sending that. Please try again." });
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseFrame(frame);
      if (event) onEvent(event);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

function parseFrame(frame: string): TurnEvent | null {
  let name = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) name = line.slice(7);
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  if (!name || !data) return null;
  try {
    return { type: name, ...(JSON.parse(data) as object) } as TurnEvent;
  } catch {
    return null;
  }
}
