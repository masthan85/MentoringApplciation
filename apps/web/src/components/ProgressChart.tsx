"use client";

import { useState } from "react";

export type Series = { id: string; title: string; points: { at: string; score: number }[] };

// Categorical colours in fixed order (blue, orange, aqua, yellow), light-mode steps.
const COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];
const W = 560;
const H = 220;
const PAD = { l: 36, r: 12, t: 12, b: 28 };

export function ProgressChart({ series }: { series: Series[] }) {
  const [table, setTable] = useState(false);
  const shown = series.filter((s) => s.points.length > 0).slice(0, COLOURS.length);
  const times = shown.flatMap((s) => s.points.map((p) => Date.parse(p.at)));
  if (shown.length === 0) return <p style={{ color: "var(--muted)" }}>Scores will appear here once you have recorded some.</p>;
  const lo = Math.min(...times);
  const hi = Math.max(...times);
  const x = (t: number) => PAD.l + (hi === lo ? (W - PAD.l - PAD.r) / 2 : ((t - lo) / (hi - lo)) * (W - PAD.l - PAD.r));
  const y = (v: number) => PAD.t + ((2 - v) / 4) * (H - PAD.t - PAD.b);

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">Goal attainment over time (−2 to +2)</figcaption>
      {table ? (
        <table className="w-full text-sm">
          <thead>
            <tr><th className="text-left">Goal</th><th className="text-left">Date</th><th className="text-left">Level</th></tr>
          </thead>
          <tbody>
            {shown.flatMap((s) => s.points.map((p, i) => (
              <tr key={`${s.id}-${i}`}><td>{s.title}</td><td>{p.at}</td><td>{p.score > 0 ? "+" : ""}{p.score}</td></tr>
            )))}
          </tbody>
        </table>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Line chart of goal levels for ${shown.map((s) => s.title).join(", ")}`} className="w-full">
          {[-2, -1, 0, 1, 2].map((v) => (
            <g key={v}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="currentColor" opacity={v === 0 ? 0.35 : 0.12} strokeWidth={1} />
              <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end" fontSize={11} fill="currentColor" opacity={0.7}>{v > 0 ? `+${v}` : v}</text>
            </g>
          ))}
          {shown.map((s, i) => (
            <g key={s.id}>
              <polyline fill="none" stroke={COLOURS[i]} strokeWidth={2} strokeLinejoin="round" points={s.points.map((p) => `${x(Date.parse(p.at))},${y(p.score)}`).join(" ")} />
              {s.points.map((p, j) => (
                <circle key={j} cx={x(Date.parse(p.at))} cy={y(p.score)} r={4} fill={COLOURS[i]} stroke="var(--background)" strokeWidth={2}>
                  <title>{`${s.title}: ${p.score > 0 ? "+" : ""}${p.score} on ${p.at}`}</title>
                </circle>
              ))}
            </g>
          ))}
          <text x={PAD.l} y={H - 8} fontSize={11} fill="currentColor" opacity={0.7}>{new Date(lo).toISOString().slice(0, 10)}</text>
          <text x={W - PAD.r} y={H - 8} textAnchor="end" fontSize={11} fill="currentColor" opacity={0.7}>{new Date(hi).toISOString().slice(0, 10)}</text>
        </svg>
      )}
      <ul className="flex flex-wrap gap-4 text-sm" aria-label="Legend">
        {shown.map((s, i) => (
          <li key={s.id} className="flex items-center gap-1">
            <span aria-hidden className="inline-block h-2 w-4 rounded" style={{ background: COLOURS[i] }} />
            {s.title}
          </li>
        ))}
      </ul>
      <button type="button" className="text-sm underline" onClick={() => setTable(!table)}>
        {table ? "Show chart" : "Show as table"}
      </button>
    </figure>
  );
}
