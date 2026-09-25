import { cn } from "@/lib/cn";
import { BASELINE_COLORS } from "@/lib/format";
import type { BaselineConfidence } from "@/types/domain";

export function BaselineStatus({ confidence }: { confidence: BaselineConfidence }) {
  return (
    <span className={cn("inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider", BASELINE_COLORS[confidence])}>
      {confidence === "INSUFFICIENT" ? "Insufficient baseline" : confidence === "LIMITED" ? "Limited baseline" : "Established baseline"}
    </span>
  );
}
