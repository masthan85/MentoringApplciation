import { apiBaseUrl } from "@/lib/api/client";

export const dynamic = "force-dynamic";

type Readiness = { status: string; checks: Record<string, string> };

async function readiness(): Promise<Readiness | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/readyz`, { cache: "no-store" });
    return (await response.json()) as Readiness;
  } catch {
    return null;
  }
}

export default async function Home() {
  const status = await readiness();
  return (
    <main id="main" className="mx-auto max-w-2xl px-4 py-16 sm:py-24">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Mentor</h1>
      <p className="mt-4 text-lg" style={{ color: "var(--muted)" }}>
        A mentor for data, AI and software careers that remembers your goals, holds you to your
        commitments and works alongside your human mentors.
      </p>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        You are talking to an AI. It does not claim human experience or professional
        qualifications.
      </p>
      <section
        aria-labelledby="status"
        className="mt-12 rounded-lg border p-4"
        style={{ borderColor: "var(--line)" }}
      >
        <h2 id="status" className="text-sm font-medium uppercase tracking-wide">
          Service status
        </h2>
        {status ? (
          <ul className="mt-2 text-sm">
            <li>Overall: {status.status}</li>
            {Object.entries(status.checks).map(([name, value]) => (
              <li key={name}>
                {name}: {value}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm">The API is not reachable.</p>
        )}
      </section>
    </main>
  );
}
