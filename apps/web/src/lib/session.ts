"use client";

// Development sign-in. The API only mounts /v1/dev/login when AUTH_MODE=dev. A real identity
// provider (Auth0, Clerk or Entra) replaces this file; nothing else needs to change because the
// API only verifies bearer tokens.

import { publicApiUrl } from "./api/client";

const KEY = "mentor.token";

export function getToken(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function signOut(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
}

export async function signIn(email: string): Promise<void> {
  const response = await fetch(`${publicApiUrl}/v1/dev/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) throw new Error("Sign-in failed");
  const { access_token } = (await response.json()) as { access_token: string };
  window.sessionStorage.setItem(KEY, access_token);
}
