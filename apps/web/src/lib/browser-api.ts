"use client";

import { api, publicApiUrl } from "./api/client";
import { getToken } from "./session";

// Attach the bearer token to every typed request.
let installed = false;
export function installAuth(): void {
  if (installed) return;
  installed = true;
  api.use({
    onRequest({ request }) {
      const token = getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  });
}

export { api };

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function download(path: string, filename: string): Promise<void> {
  const response = await fetch(`${publicApiUrl}${path}`, { headers: authHeaders() });
  if (!response.ok) throw new Error("Download failed");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
