import { baselineView } from "@/lib/assessment";
import { cn } from "@/lib/cn";
import type { BaselineConfidence } from "@/types/domain";

const TONE: Record<string, string> = {
  full: "border-sev-low/40 bg-sev-low/5", discounted: "border-sev-medium/50 bg-sev-medium/5", none: "border-base-600 bg-base-800",
};

/** States, in words, how much a facility baseline is allowed to count. Limited history is never called an established twin. */
export function BaselineBanner({ status, hasFacility, contribution, cap }: { status: BaselineConfidence | null | undefined; hasFacility: boolean; contribution?: number | null; cap?: number | null }) {
  const v = baselineView(status, hasFacility);
  return (
    <div className={cn("mb-3 rounded border px-3 py-2", TONE[v.weight])} data-testid="baseline-banner">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.1em] text-base-100">{v.label}</span>
        {contribution != null && cap != null && (
          <span className="font-mono text-[11px] text-base-300">
            deviation contribution to risk: +{contribution.toFixed(1)} pts (max +{cap.toFixed(1)} under this baseline)
          </span>
        )}
      </div>
      {v.caution && <p className="mt-1 text-xs text-base-200">{v.caution}</p>}
    </div>
  );
}
