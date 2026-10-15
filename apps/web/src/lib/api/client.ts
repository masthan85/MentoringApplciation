import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Server components use the internal URL; the browser always uses the public one.
export const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const apiBaseUrl = process.env.API_INTERNAL_URL ?? publicApiUrl;

export const api = createClient<paths>({ baseUrl: publicApiUrl });
