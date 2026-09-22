import { cn } from "@/lib/cn";
import { BASELINE_COLORS } from "@/lib/format";
import type { BaselineConfidence } from "@/types/domain";

export function BaselineStatus({ confidence }: { confidence: BaselineConfidence }) {
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-1 text-xs font-semibold uppercase tracking-wide", BASELINE_COLORS[confidence])}>
      {confidence === "INSUFFICIENT" ? "Insufficient baseline" : `${confidence} baseline`}
    </span>
  );
}
