import { cn } from "@/lib/cn";
import { SEVERITY_COLORS } from "@/lib/format";
import type { Severity } from "@/types/domain";

export function RiskBadge({ severity, score, size = "md" }: { severity: Severity | null; score?: number | null; size?: "sm" | "md" }) {
  if (!severity) {
    return <span className="rounded border border-base-500/40 bg-base-700/40 px-2 py-0.5 text-xs text-base-300">UNSCORED</span>;
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border font-semibold uppercase tracking-wide",
        SEVERITY_COLORS[severity],
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs"
      )}
    >
      {severity}
      {score !== undefined && score !== null && <span className="font-mono font-normal opacity-80">{Math.round(score)}</span>}
    </span>
  );
}
