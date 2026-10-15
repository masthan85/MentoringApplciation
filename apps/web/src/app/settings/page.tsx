"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, download } from "@/lib/browser-api";
import { signOut } from "@/lib/session";

type Billing = { billing_enabled: boolean; plan: string; plan_name: string; daily_turns: number | null; features: Record<string, boolean>; can_manage: boolean };
type Access = { at: string; action: string; by: string; resource_type: string | null };

export default function SettingsPage() {
  return (
    <AppShell>
      <Settings />
    </AppShell>
  );
}

function Settings() {
  const router = useRouter();
  const [billing, setBilling] = useState<Billing | null>(null);
  const [log, setLog] = useState<Access[]>([]);
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void (async () => {
      const [b, a] = await Promise.all([api.GET("/v1/billing"), api.GET("/v1/privacy/access-log")]);
      if (b.data) setBilling(b.data as unknown as Billing);
      if (a.data) setLog(a.data as unknown as Access[]);
    })();
  }, []);

  async function go(path: "/v1/billing/checkout" | "/v1/billing/portal", plan?: "mentor" | "mentor_human") {
    const { data } =
      path === "/v1/billing/checkout"
        ? await api.POST(path, { body: { plan: plan! } })
        : await api.POST(path);
    if (data) window.location.href = (data as { url: string }).url;
    else setMessage("Billing is unavailable just now.");
  }

  async function remove(event: React.FormEvent) {
    event.preventDefault();
    const { response } = await api.POST("/v1/privacy/delete-account", { body: { confirm } });
    if (response.status === 204) {
      signOut();
      router.replace("/");
    } else setMessage('To confirm, type "delete my account".');
  }

  return (
    <div className="space-y-10">
      <h1 className="text-xl font-semibold">Settings</h1>

      <section aria-labelledby="plan-h" className="space-y-2">
        <h2 id="plan-h" className="font-medium">Plan</h2>
        {billing && (
          <>
            <p>
              {billing.billing_enabled ? `You are on the ${billing.plan_name} plan.` : "Billing is not switched on, so everything is available."}
              {billing.daily_turns ? ` Free plan: ${billing.daily_turns} messages a day.` : ""}
            </p>
            {billing.billing_enabled && (
              <div className="flex gap-3 text-sm">
                {billing.plan === "free" && <button className="rounded border px-3 py-1" style={{ borderColor: "var(--line)" }} onClick={() => void go("/v1/billing/checkout", "mentor")}>Choose Mentor</button>}
                {billing.plan !== "mentor_human" && <button className="rounded border px-3 py-1" style={{ borderColor: "var(--line)" }} onClick={() => void go("/v1/billing/checkout", "mentor_human")}>Choose Mentor + Human</button>}
                {billing.can_manage && <button className="rounded border px-3 py-1" style={{ borderColor: "var(--line)" }} onClick={() => void go("/v1/billing/portal")}>Manage subscription</button>}
              </div>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="people-h" className="space-y-2">
        <h2 id="people-h" className="font-medium">Human mentor</h2>
        <p style={{ color: "var(--muted)" }}>Invite a mentor you work with. They only see a brief that you write and approve.</p>
        <Link href="/mentor-link" className="underline underline-offset-4">Manage your mentor link</Link>
        {" · "}
        <Link href="/mentor" className="underline underline-offset-4">I am a mentor</Link>
      </section>

      <section aria-labelledby="data-h" className="space-y-3">
        <h2 id="data-h" className="font-medium">Your data</h2>
        <p style={{ color: "var(--muted)" }}>Memories, sharing choices and your writing style are managed in <Link href="/notes" className="underline">My notes</Link>.</p>
        <button className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }} onClick={() => void download("/v1/privacy/export", "mentor-export.json")}>
          Download everything
        </button>
        <div>
          <h3 className="text-sm font-medium">Who has accessed your data</h3>
          {log.length === 0 ? <p className="text-sm" style={{ color: "var(--muted)" }}>Nothing yet.</p> : (
            <ul className="mt-1 space-y-1 text-sm">
              {log.slice(0, 20).map((e, i) => (
                <li key={i}>{e.at.slice(0, 16).replace("T", " ")} · {e.action} · by {e.by}</li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <form onSubmit={remove} className="space-y-2" aria-labelledby="delete-h">
        <h2 id="delete-h" className="font-medium">Delete my account</h2>
        <p className="text-sm" style={{ color: "var(--muted)" }}>This removes your profile, conversations, goals, drafts and memories for good. Download your data first if you want a copy.</p>
        <label className="block text-sm">
          Type &quot;delete my account&quot; to confirm
          <input value={confirm} onChange={(e) => setConfirm(e.target.value)} className="mt-1 block rounded border bg-transparent p-2" style={{ borderColor: "var(--line)" }} />
        </label>
        <button className="rounded border px-3 py-1 text-sm" style={{ borderColor: "var(--line)" }}>Delete everything</button>
        {message && <p role="alert" className="text-sm">{message}</p>}
      </form>
    </div>
  );
}
