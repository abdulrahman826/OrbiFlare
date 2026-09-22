import { cn } from "@/lib/cn";
import { TRAJECTORY_COLORS, TRAJECTORY_LABEL } from "@/lib/format";
import type { TrajectoryDirection } from "@/types/domain";

const ARROWS: Record<TrajectoryDirection, string> = {
  STABLE: "→",
  INCREASING: "↗",
  ESCALATING: "↗↗",
  DECREASING: "↘",
  INSUFFICIENT_DATA: "–",
};

export function TrajectoryBadge({ direction }: { direction: TrajectoryDirection | null }) {
  const d = direction ?? "INSUFFICIENT_DATA";
  return (
    <span className={cn("inline-flex items-center gap-1 rounded border px-2 py-1 text-xs font-medium", TRAJECTORY_COLORS[d])}>
      <span className="font-mono">{ARROWS[d]}</span>
      {TRAJECTORY_LABEL[d]}
    </span>
  );
}
