"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api, installAuth } from "@/lib/browser-api";
import { NotificationBell } from "@/components/NotificationBell";
import { getToken, signOut } from "@/lib/session";

const links = [
  { href: "/today", label: "Today" },
  { href: "/chat", label: "Mentor" },
  { href: "/studio", label: "Studio" },
  { href: "/notes", label: "My notes" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  // The token lives in sessionStorage, which the server cannot see: render nothing until the
  // browser confirms there is one.
  const signedIn = useSyncExternalStore(
    () => () => {},
    () => getToken() !== null,
    () => false,
  );

  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    installAuth();
    if (!getToken()) {
      router.replace("/");
      return;
    }
    void (async () => {
      const { data } = await api.GET("/v1/me");
      setIsAdmin(Boolean(data?.is_admin));
    })();
  }, [router]);

  const visible = isAdmin ? [...links, { href: "/admin/sources", label: "Sources" }, { href: "/admin/evals", label: "Evals" }] : links;

  if (!signedIn) return null;

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4">
      <header className="flex items-center justify-between py-4">
        <nav aria-label="Main" className="flex gap-4 text-sm">
          {visible.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname.startsWith(link.href) ? "page" : undefined}
              className={pathname.startsWith(link.href) ? "font-medium underline underline-offset-4" : ""}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-4">
          <NotificationBell />
        <button
          className="text-sm"
          style={{ color: "var(--muted)" }}
          onClick={() => {
            signOut();
            router.replace("/");
          }}
        >
          Sign out
        </button>
        </div>
      </header>
      <main id="main" className="flex-1 pb-8">
        {children}
      </main>
      <footer className="py-4 text-xs" style={{ color: "var(--muted)" }}>
        You are talking to an AI. It does not have human experience or professional
        qualifications, and it is not a substitute for legal, medical, financial or mental health advice.
      </footer>
    </div>
  );
}
