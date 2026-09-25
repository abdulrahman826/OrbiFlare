import { cn } from "@/lib/cn";

const TONES = {
  default: "text-base-100",
  warn: "text-sev-medium",
  high: "text-sev-high",
  critical: "text-sev-critical",
  good: "text-sev-low",
} as const;

/** Typographic summary figure: hierarchy from size and position, not from a coloured box. */
export function KPI({ label, value, sub, tone = "default" }: { label: string; value: string | number; sub?: string; tone?: keyof typeof TONES }) {
  return (
    <div className="border-l-2 border-base-600 py-0.5 pl-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-base-400">{label}</div>
      <div className={cn("mt-0.5 font-mono text-[26px] font-medium leading-none", TONES[tone])}>{value}</div>
      {sub && <div className="mt-1 text-[11px] text-base-400">{sub}</div>}
    </div>
  );
}
