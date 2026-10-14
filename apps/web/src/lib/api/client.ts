import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Server-side calls use the internal URL; the browser uses the public one.
export const apiBaseUrl =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl: apiBaseUrl });
