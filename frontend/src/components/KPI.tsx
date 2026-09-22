import { cn } from "@/lib/cn";

export function KPI({ label, value, sub, tone }: { label: string; value: string | number; sub?: string; tone?: "default" | "warn" | "critical" }) {
  return (
    <div className="rounded-md border border-base-700 bg-base-850 px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-base-300">{label}</div>
      <div
        className={cn(
          "mt-1 font-mono text-2xl font-semibold",
          tone === "critical" ? "text-sev-critical" : tone === "warn" ? "text-sev-medium" : "text-base-100"
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-0.5 text-[11px] text-base-400">{sub}</div>}
    </div>
  );
}
