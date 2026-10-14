"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api, installAuth } from "@/lib/browser-api";
import { getToken, signIn } from "@/lib/session";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);
  const hasToken = useSyncExternalStore(
    () => () => {},
    () => getToken() !== null,
    () => false,
  );

  async function route() {
    installAuth();
    const { data } = await api.GET("/v1/profile");
    router.replace(data?.onboarding_status === "complete" ? "/chat" : "/onboarding");
  }

  useEffect(() => {
    if (!getToken()) return;
    void (async () => {
      installAuth();
      const { data } = await api.GET("/v1/profile");
      if (data) router.replace(data.onboarding_status === "complete" ? "/chat" : "/onboarding");
      else setChecking(false);
    })().catch(() => setChecking(false));
  }, [router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await signIn(email);
      await route();
    } catch {
      setError("Could not sign in. Is the API running?");
    }
  }

  if (checking && hasToken) return null;

  return (
    <main id="main" className="mx-auto max-w-xl px-4 py-16 sm:py-24">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Mentor</h1>
      <p className="mt-4 text-lg" style={{ color: "var(--muted)" }}>
        A mentor for data, AI and software careers that remembers your goals, holds you to your
        commitments and works alongside your human mentors.
      </p>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        You will be talking to an AI. It does not claim human experience or professional
        qualifications. You can see, correct and delete everything it remembers. For adults only.
      </p>
      <form onSubmit={submit} className="mt-10 flex flex-col gap-3">
        <label htmlFor="email" className="text-sm font-medium">
          Email address (development sign-in)
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-md border bg-transparent px-3 py-2"
          style={{ borderColor: "var(--line)" }}
        />
        <button
          type="submit"
          className="self-start rounded-md px-4 py-2 text-sm font-medium"
          style={{ background: "var(--accent)", color: "var(--background)" }}
        >
          Continue
        </button>
        <p role="alert" className="text-sm" style={{ color: "#b3261e" }}>
          {error}
        </p>
      </form>
    </main>
  );
}
