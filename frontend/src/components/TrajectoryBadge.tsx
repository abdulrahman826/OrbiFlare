import { cn } from "@/lib/cn";
import { TRAJECTORY_COLORS, TRAJECTORY_LABEL } from "@/lib/format";
import type { TrajectoryDirection } from "@/types/domain";

const ARROWS: Record<TrajectoryDirection, string> = {
  STABLE: "→",
  INCREASING: "↗",
  ESCALATING: "⇈",
  DECREASING: "↘",
  INSUFFICIENT_DATA: "–",
};

export function TrajectoryBadge({ direction }: { direction: TrajectoryDirection | null }) {
  const d = direction ?? "INSUFFICIENT_DATA";
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", TRAJECTORY_COLORS[d])}>
      <span className="font-mono">{ARROWS[d]}</span>
      {TRAJECTORY_LABEL[d]}
    </span>
  );
}
